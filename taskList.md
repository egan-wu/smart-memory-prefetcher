# Task List: RL-Based Smart Memory Prefetcher (ChampSim 實作專案)

本文件定義了次世代遊戲主機智慧型記憶體預取器專案的各階段實作任務。

---

## Task 1: ChampSim 環境建置與基準線 (Baseline) 建立
* **預期目標:** 成功編譯 ChampSim 並使用傳統硬體預取器跑出具備參考價值的效能基準線。
* **實作方式:** * Clone ChampSim 官方儲存庫。
    * 設定 `champsim_config.json`，配置對標現代遊戲主機的規格（如 L1/L2/LLC 大小、DRAM 頻寬與延遲）。
    * 使用內建的 `next_line` 或 `ip_stride` 作為 L2/L3 的預取策略進行編譯。
* **技術細節:** 撰寫 bash 腳本批次執行多個 Trace 檔案，並自動解析輸出的文字檔以擷取關鍵數據。
* **產出物:** `baseline_results.csv` (記錄不同 Traces 的基準效能)。
* **所需資源/前置條件:** Linux 環境 (或 WSL2)、G++ 編譯器、基礎的 Memory Access Traces (如 SPEC CPU 或圖形運算 Traces)。
* **驗證指標:** IPC (Instructions Per Cycle), MPKI (Misses Per Kilo Instructions), DRAM 頻寬使用率 (GB/s)。

## Task 2: 記憶體存取軌跡 (Memory Trace) 提取與特徵工程
* **預期目標:** 將純文字的 Memory Traces 轉換為適合訓練神經網路的結構化資料 (State-Action Pairs)。
* **實作方式:** 撰寫 Python 腳本讀取 ChampSim 能接受的 Trace 格式，或是在 ChampSim 中掛載探針 (Probe) 導出快取未命中 (Cache Miss) 的紀錄。
* **技術細節:** * 提取特徵包含：Program Counter (PC) 的 Hash 值。
    * 計算連續存取的位址差值 (Address Delta, $\Delta_t$)。
    * 將歷史 $N$ 筆存取紀錄打包成一個時間序列矩陣 (Sliding Window)。
* **產出物:** `training_data.npy` 或 `training_data.csv`。
* **所需資源/前置條件:** Python, Numpy, Pandas。
* **驗證指標:** 資料集大小、特徵維度確認、Delta 分布的直方圖 (確認是否有明顯的空間局部性 Spatial Locality)。

## Task 3: 輕量級強化學習模型設計與離線訓練 (PyTorch)
* **預期目標:** 訓練出一個能精準預測下一個存取位址，且架構極小的 AI 代理 (Agent)。
* **實作方式:** 使用 PyTorch 建立 Deep Q-Network (DQN) 或基礎的 Multi-Layer Perceptron (MLP)。
* **技術細節:**
    * **State:** 歷史 PC 與 Address Deltas。
    * **Action:** 預測的 Delta Offset (例如 $0, +1, +2...$)，$0$ 表示不預取。
    * **Reward:** 預取命中給予高正分 ($+10$)，快取污染給予負分 ($-5$)，頻寬過載給予懲罰 ($-2$)。
    * 隱藏層 (Hidden Layers) 限制在 2-3 層以內，神經元數量不超過 128，確保硬體化可行性。
* **產出物:** 訓練完成的權重檔 `model_weights.pth` 與訓練收斂曲線圖。
* **所需資源/前置條件:** PyTorch 環境、NVIDIA GPU (加速訓練)。
* **驗證指標:** 離線驗證集 (Validation Set) 上的預測準確率 (Accuracy)、Reward 收斂趨勢。

## Task 4: 模型權重匯出與純 C++ 推論引擎實作 (HW/SW Co-design)
* **預期目標:** 將 Python 訓練好的模型轉換為零依賴 (Zero-dependency) 的 C++ 程式碼，模擬 ASIC 硬體寫死權重的行為。
* **實作方式:** 撰寫 Python 腳本將 `.pth` 內的矩陣數值讀出，並格式化輸出為 C++ 的標頭檔。
* **技術細節:**
    * 生成 `weights.h`，將權重宣告為 `constexpr std::array`。
    * 撰寫純 C++ 的矩陣乘法與 ReLU 激勵函數。
    * **嚴格限制:** 推論過程中絕對禁止使用動態記憶體分配 (`new`/`malloc`/`std::vector`)。
* **產出物:** `weights.h` 與 `inference_engine.hpp`。
* **所需資源/前置條件:** 基礎的線性代數知識與現代 C++17 特性運用。
* **驗證指標:** C++ 推論結果必須與 PyTorch 的輸出達到 $10^{-5}$ 以內的浮點數精確度一致。

## Task 5: ChampSim 預取器整合與端到端模擬
* **預期目標:** 讓 AI 模型在 ChampSim 模擬器內部即時控制快取的預取行為。
* **實作方式:** 在 ChampSim 的 `prefetcher/` 資料夾下新建模組，引入 Task 4 的 C++ 推論引擎。
* **技術細節:**
    * 實作 `prefetcher_operate()`：收集當前狀態，呼叫推論引擎，發送預取請求。
    * 實作 `prefetcher_cache_fill()`：更新內部 State 暫存區 (Buffer)。
    * 處理 C++ 的模組編譯與依賴關係。
* **產出物:** `rl_prefetcher.cc` 原始碼。
* **所需資源/前置條件:** 對 ChampSim API 的理解。
* **驗證指標:** 編譯成功且在執行模擬時沒有 Segmentation Fault 或 Memory Leak。

## Task 6: 架構量化分析與硬體開銷評估 (Architectural Evaluation)
* **預期目標:** 產出面試用的最終技術報告，證明此 AI 架構的商業與技術價值。
* **實作方式:** 收集 Task 5 的輸出日誌，與 Task 1 的基準線進行交叉比對。撰寫理論硬體開銷評估。
* **技術細節:**
    * **效能評估:** 計算 IPC 提升的百分比，分析頻寬節省量。
    * **硬體開銷 (SRAM Area):** 計算儲存特徵 Buffer 與模型權重所需的 SRAM 容量 (Bytes)。
    * **推論潛時 (Latency):** 估算矩陣乘法所需的 MAC 數量，論述在硬體 Pipeline 中如何隱藏這段計算時間。
* **產出物:** 專案 Readme 或簡報 (包含 Pareto Frontier 分析圖表與架構比較圖)。
* **所需資源/前置條件:** 數據視覺化工具 (Python Matplotlib/Seaborn)。
* **驗證指標:** 報告的邏輯推演是否能說服資深架構師 (Trade-off 分析是否合理)。