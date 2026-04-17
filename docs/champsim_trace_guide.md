# ChampSim Trace 與 DQN 訓練資料轉換指南

本文件詳細介紹在「智慧型記憶體預取器」專案中，如何從 ChampSim 取得記憶體軌跡 (Trace)、萃取關鍵特徵，並將其轉換為可用於深度強化學習 (DQN) 的訓練資料。

---

## 1. 我們可以從 ChampSim 取得什麼 Trace？

ChampSim 是透過讀取真實或合成的應用程式執行紀錄（Trace）來進行模擬的。每個 Trace 檔案（通常是以 `.champsimtrace.xz` 或 `.gz` 壓縮的二進位檔）本質上是由數千萬到數十億筆的**指令紀錄 (Instruction Records)** 所組成。

在 ChampSim 的預設格式中，每筆紀錄通常佔用 48 bytes 到 64 bytes 不等，包含該指令在執行當下最重要的架構資訊。具體來說，每一筆紀錄包含：

* **Instruction Pointer (IP / PC):** 指令所在的記憶體位址（即程式計數器）。
* **Branch Info:** 該指令是否為分支指令 (Branch)，以及分支是否被觸發 (Taken)。
* **Source Registers / Destination Registers:** 暫存器讀寫的依賴關係（用於模擬亂序執行的 ROB）。
* **Memory Addresses (最關鍵):**
  * `Load (Destination) Addresses`: 該指令從記憶體中**讀取**資料的真實位址（最多 2 個）。
  * `Store (Source) Addresses`: 該指令**寫入**資料到記憶體的真實位址（最多 2 個）。

> **重點：** 對於預取器專案，我們**只關心會觸發記憶體讀取的指令 (Load Instructions)**。如果一筆紀錄沒有 Load Address，我們在特徵萃取時會直接忽略它。

---

## 2. Trace 中可獲取哪些特徵？此特徵的重要性？

從上述的原始紀錄中，我們直接或間接提取出以下三個核心特徵來訓練預取器：

### A. Program Counter (PC)
* **原始資料：** 64-bit 的指令記憶體位址（例如 `0x0000000000401A30`）。
* **重要性：** **區分不同行為模式的關鍵。** 同一個應用程式（如遊戲）中，負責「循序讀取連續陣列」的程式碼，跟負責「在場景圖中隨機追蹤指標」的程式碼，位在不同的 PC 上。將 PC 考慮進來（Per-PC Tracking），AI 才能學會：「當這行程式碼執行時，應該大膽預取；當那行程式碼執行時，最好不要亂猜以避免快取污染。」

### B. 記憶體區塊位址 (Block Address / Cache Line Address)
* **原始資料：** `Load Address`（例如 `0x00000001000A1024`）。
* **處理方式：** 硬體快取是以 Cache Line（通常為 64 Bytes）為單位的。因此我們必須把絕對位址向右位移 6 個 bits (`Address >> 6`)，得到 Block Address。
* **重要性：** 預取器一次只能搬運一個 Cache Line。如果兩次連續的記憶體讀取落在同一個 Cache Line 裡，對預取器來說是「無效資訊」，因為資料已經被搬進來了。只有跨越 Cache Line 的讀取才有預測價值。

### C. 位址差值 (Address Delta)
* **特徵轉換：** `Delta = 當前 Block Address - 前一次讀取的 Block Address`。
* **重要性：** **最核心的學習特徵。** 神經網路絕對不能學習「絕對位址」，因為每次執行程式時作業系統給的記憶體空間都不同。神經網路必須學習「空間位移的規律」，例如 `+1` (循序讀取), `+4` (Stride 讀取), 或是不斷變動的 Delta (指標追蹤)。

---

## 3. 該怎麼將特徵轉換成 Input 數據？

在理解了特徵後，我們如何將這些流水帳般的紀錄轉換成 AI 網路一次推理所需的 `Input` 向量？我們採用 **Per-PC Sliding Window (每行程式獨立的滑動視窗)** 架構：

1. **PC Hash (降維):**
   真實的 64-bit PC 太長，而且很稀疏。為了符合硬體限制，我們會對 PC 進行簡單的位元運算雜湊 (Hash)，把它壓縮到 10-bit 到 12-bit 的空間中（如 `pc_hash = (ip ^ (ip >> 2)) & 0x3FF`）。
2. **維護歷史視窗:**
   針對每個不同的 `PC Hash`，我們在記憶體裡維護一個長度為 $N$（例如 $N=8$）的歷史讀取紀錄陣列。
3. **計算 Input Vector:**
   當該 PC 發生第 9 次跨快取行 (Cache Line) 的讀取時：
   * 將前 8 次讀取轉換成連續的差值（Delta）。
   * 為了避免差值過大導致神經網路梯度爆炸，我們會將 Delta 截斷在一個合理的範圍內（例如 `[-128, +127]`）。
   * **最終 Input 陣列 (1D Array):** `[ PC_Hash, Delta_1, Delta_2, ..., Delta_8 ]`。這就是準備送進 MLP 網路的一筆特徵。

---

## 4. 這些數據該怎麼樣被轉換成 DQN 的訓練資料？

要訓練強化學習模型 (DQN)，我們需要的是一組組的 **State, Action, Reward** (或用於 Offline 監督式訓練的 State-Action Pairs)。

特徵轉換腳本 (`scripts/extract_features.py`) 就是負責產生這個對應關係：

### State (狀態 $S_t$)
就是我們在步驟 3 計算出來的 `Input Vector`。
* 代表意義：「AI，這是 PC=123 過去 8 次的記憶體跳躍紀錄，請判斷下一步要跳哪裡？」

### Action Label (標準答案 / 行動 $A_t$)
DQN 需要預測下一個動作，而我們的「歷史 Trace」本身就已經包含了未來！
* 當我們站在時間點 $T$ 時，我們往前偷看時間點 $T+1$ 的讀取位址。
* 計算出未來的跳躍：`Future_Delta = Block_Addr(T+1) - Block_Addr(T)`。
* **離散化 Action：** 因為我們是硬體預取器，不可能往前預取無限遠的記憶體。我們定義一個有限的 Action Space（例如 9 個選項：`[-4, -3, -2, -1, 0, +1, +2, +3, +4]`）。
  * 如果 `Future_Delta` 是 `+2`，那這筆資料的標籤就是對應 `+2` 的 Action 類別。
  * 如果 `Future_Delta` 太大（例如跳了 `+1000`），我們將標籤設為 `0` (不預取)。這是在教導模型：「當規律超出我們能預取的範圍時，最好按兵不動，才不會引發快取污染。」

### Reward Design (隱含於離線訓練中)
雖然我們產生的是類似監督式學習的 `(State, Label)` 數據對，但在後續訓練 DQN 時：
* 網路如果預測出正確的 Action (命中 Label)，我們會給予 Reward `+10`。
* 如果網路預測出 `Action 0`（無論 Label 是什麼），給予 Reward `0` (安全牌)。
* 如果網路預測了非零的 Action 但卻沒有命中 Label（這代表引發了**快取污染**），我們會給予嚴厲的懲罰 `Reward = -5`。

### 最終產出
腳本最終會產生形如 `training_data.npz` 的結構化資料庫，裡面包含兩大矩陣：
1. `X`: Shape `(Samples, 9)`，存放數百萬筆的 `[PC_Hash, 8個Delta]` 狀態特徵。
2. `y`: Shape `(Samples,)`，存放每筆狀態對應的目標 Action (0~8)。

這份資料可以直接餵進 PyTorch 進行批次訓練，從而訓練出精準輕巧的預取神經網路。