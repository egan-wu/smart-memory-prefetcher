# 專案指引：RL-Based Smart Memory Prefetcher

## 專案目標 (Project Context)
本專案為次世代遊戲主機架構設計的驗證專案，旨在透過強化學習 (RL) 取代傳統硬體預取器，解決高度碎片化存取導致的 Cache Pollution 與記憶體頻寬浪費問題。實作分為 Python 離線訓練與 ChampSim (C++) 推論整合兩部分。

## 技術棧 (Tech Stack)
* **模擬器：** ChampSim (Trace-Driven Simulator)
* **系統語言：** 現代 C++ (C++17/20)
* **AI 訓練：** Python 3.10+, PyTorch

## 建置與測試指令 (Build & Run Commands)
* **編譯 ChampSim：**
    ```bash
    ./build_champsim.sh bimodal no no no no lru 1
    ```
    *(註：依照實際 config JSON 或建置腳本修改)*
* **執行模擬：**
    ```bash
    ./run_champsim.sh bimodal-no-no-no-no-lru-1core 10 10 <trace_file.xz>
    ```
* **Python 模型訓練：**
    ```bash
    python scripts/train_rl_model.py --trace_dir ./traces --output ./weights
    ```

## 程式碼撰寫準則 (Coding Guidelines)

### 1. C++ 系統開發規範 (ChampSim 整合)
* **效能至上 (Zero-Allocation)：** 在 `prefetcher_operate()` 等熱點函式 (Hot paths) 中，**絕對禁止**使用 `new`, `malloc` 或任何動態記憶體分配。所有暫存器與狀態都應預先宣告為固定大小的 Array 或 `std::array`。
* **現代 C++ 特性：** 善用 `std::unique_ptr` (若在初始化階段)、`constexpr` (用於編譯期常數與模型權重)、以及 `inline` 函式來消除呼叫開銷。
* **快取友善 (Cache-friendly)：** 資料結構的設計需考慮記憶體對齊 (Memory Alignment) 與 Spatial Locality，避免 false sharing 或過多的 pointer chasing。

### 2. AI 模型與硬體化思維 (HW/SW Co-design)
* **極簡網路結構：** 模型推論邏輯必須是能輕易轉換為硬體邏輯閘 (ASIC/MAC units) 的簡單數學運算。避免使用複雜的激勵函數，優先考慮 ReLU。
* **無外部依賴推論：** C++ 端不可引入任何第三方 AI 函式庫 (如 LibTorch, ONNX Runtime)。權重需透過 Python 腳本匯出為扁平化的 C++ 標頭檔 (`weights.h`)，並用純 C++ 迴圈完成矩陣乘法推論。

### 3. Git 與註解規範
* **註解語言：** 程式碼註解與架構說明請以清楚的英文或繁體中文撰寫，重點在於解釋「為什麼要這樣設計 (Why)」，以及「硬體資源的 Trade-off 是什麼」。
* **Git Commits：** 使用 Conventional Commits 格式 (例如 `feat(prefetcher): implement state extraction buffer`)。

### 特殊指令處理
當被要求分析效能或除錯時，請優先從「記憶體階層 (Memory Hierarchy) 的延遲」與「DRAM 頻寬佔用率」的角度來思考根本原因。