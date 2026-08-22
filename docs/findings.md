# iCE40 探針：Claim B 的主機端證據與邊界

日期：2026-08-22  
平台：iCESugar v1.5 / iCE40UP5K-SG48  
狀態：主機端流程可重現；2026-08-22 無爭用實板重驗通過

對照資料：

- [CoBEA, GECCO 2022 Companion](https://nmi.informatik.uni-leipzig.de/wp-content/uploads/2022/08/cobea_gecco2022.pdf)
- [Whitley、Yoder、Carpenter, ALIFE 2021](https://doi.org/10.1162/isal_a_00448)
- [Project IceStorm](https://github.com/YosysHQ/icestorm)
- [Lattice iCE40 Programming and Configuration](https://www.latticesemi.com/-/media/LatticeSemi/Documents/ApplicationNotes/IK/FPGA-TN-02001-3-3-iCE40-Programming-Configuration.ashx?document_id=46502)

研究問題是：在沒有公開 CRAM readback 流程的平台上，device-local map
能否幫助建立比 raw mutation 更保守、可檢查的演化操作子？

## 0. 結論摘要

可以在主機端證明的，是一組有清楚邊界的結構性質：

1. LUT-INIT-only 操作子不會直接修改 IceStorm 資料庫中的 routing selection。
2. raw single-bit flip 經常會改變局部 routing entry 的匹配狀態。
3. decode-before-program 能抓到突變程式的位元索引與結構錯誤。
4. known-answer probe 必須先證明其可觀測序列能分離 baseline 與 mutant。

目前不能只靠這些腳本證明的，是完整物理安全性。IceStorm 是反向工程模型，
而且本分析未涵蓋所有 tile 類型與類比電氣行為。文中的「多驅動」均指
IceStorm 全域 configured-net graph 的候選，不等於已在矽上量到爭用。

## 1. Logic-tile coordinate 普查

UP5K 有 660 個 logic tile，每個 ASC tile 是 16 × 54 = 864 個座標。
`bitclass.py` 以安裝中的 IceStorm database 分類；「database-unreferenced」
只表示資料庫沒有引用該座標，不保證它是有效、保留或實際可作用的 CRAM bit。

| 類別 | 座標/tile | 佔比 |
|---|---:|---:|
| routing / buffer | 637 | 73.7% |
| LUT-INIT（8 LC × 16） | 128 | 14.8% |
| database-unreferenced | 57 | 6.6% |
| LC sequential/control（8 LC × 4） | 32 | 3.7% |
| 其他已映射控制 | 10 | 1.2% |

這是「IceStorm 對 logic tile 的覆蓋狀況」，不是完整晶片 map 的獨立真值。

## 2. 窮舉 single-bit flip

`exhaustive.py` 對所有非全零 logic tile 的每個座標逐一翻轉。局部效果由
tile database 判定；只要翻轉新增 route，就在 IceStorm 的全域 net graph 上檢查。
模型先把固定 span／neighbour 連線收縮成 static components，再把已啟用的
routing／buffer entries 表示為帶重數的可增刪 edge，因此 add+remove 也能在刪除
舊 edge、加入新 edge 後精確重算受影響的連通元件。

| | `leds` 稀疏設計 | `dense` 75% LC 設計 |
|---|---:|---:|
| 非全零 logic tile | 137 / 660 | 596 / 660 |
| 檢查座標 | 118,368 | 514,944 |
| baseline 已選中的局部 mux 端點 | 93 | 9,622 |
| 新 routing entry 被啟用 | 49,077（41.5%） | 202,699（39.4%） |
| route source 改接 | 351 | 36,343 |
| routing entry 被關閉 | 98 | 10,099 |
| 局部 dual-route 候選 | 13 | 1,287 |
| **全域 multi-driver net 候選** | **14（0.012%）** | **2,471（0.480%）** |
| ├ 其中局部乾淨（global-only） | 1 | 1,474 |
| └ 其中真正跨 tile | 1 | 1,473 |
| split-aware add+remove 檢查 | 351 | 36,343 |
| └ 分割後仍為 multi-driver | 0 | 0 |
| 真正 LUT-INIT-only 座標 | 17,536（14.8%） | 76,288（14.8%） |

「新 routing entry」是結構事件，不自動等於功能錯誤、寄生迴路或電氣危險；
source/destination 可能未參與可觀測功能。全域 multi-driver 檢查與局部計數是
兩個方向的修正：它會**剪掉**一部分局部 dual-route 候選（dense 1,287 中有 290
個合併後仍只有一個 driver），同時**加上**局部看不見的 global-only 類 —— 一個翻轉若
把某條線接進**全域圖上已在驅動的元件**，在本地端點只是乾淨的 0→1，局部條件
永遠不會觸發。dense 有 1,474 個這種 global-only 案例，佔全部候選的六成；其中
1,473 個含另一 tile 的 driver，另 1 個是 `(4,10) B1[52]` 在同一 tile 內經全域路徑
合併 `lutff_0/out` 與 `lutff_5/out`。兩者都仍是 IceStorm 模型推論，不是矽上量測。

同時啟用又關閉 route 的翻轉（「route source changed」）已使用上述 split-aware graph
全部重算（leds 351、dense 36,343）；這兩個 fixture 中，分割後仍為 multi-driver 的
數量都是 0。這是資料庫拓撲模型的確定結果，不等於類比電氣安全或功能安全證明。

### 安全與表達力交換

若操作子只允許 LUT-INIT，它保留全部座標中的 14.8%，放棄 85.2%。可保證的
是「不直接改變 routing selection」，不能宣稱功能風險或全部電氣風險為零。

Whitley 的方法也不是 LUT-only。該論文仍演化鄰居 routing、最多兩個輸入及
Boolean operation，只是排除 span wires、夾死 pass-through，並限制每 CLB
的可用邏輯資源。CoBEA 對抽象模型可能排除模型外解的批評仍然成立，但兩者
不宜描述為「LUT-only 與 raw mutation」的簡單兩極。

### 2026-08-22 修正：全域檢查曾被錯誤地設下前提條件

初版 `exhaustive.py` 把全域 driver 檢查包在 `if local_dual_route:` 內，導致上述
global-only 類**從未被檢查**。第一階段修正為：只要翻轉有 additions 且無 removals
就跑全域檢查。影響：leds 13 → 14、dense **997 → 2,471**（低報 2.5 倍）。第二階段
再以可刪 edge 的 split-aware graph 消除 add+remove 的 351／36,343 個 unknown；兩個
fixture 都沒有新增 multi-driver 候選。修正方向是**風險曾被低估**，因此
「map-guided operator 較保守」的結論不受影響，只是原本引用的數字偏低。
`make check-analysis` 同時釘住總數、global-only、真正 cross-tile、split-aware 計數，
以及 `(4,30) B10[53]` 的指定回歸案例。

### 獨立 oracle 交叉驗證（2026-08-22）

`work/oracle.py` 刻意不共用 `exhaustive.py` 的衝突邏輯：自行從 `ic.tile_db()`
列舉翻轉、就地修改設定、**每個翻轉重建整張 `ic.group_segments()`**，再用自己的
driver identity 計算每個元件的來源數；只 import 對方的模型**用於比對判決**，任何
歧異都會被列出並使工具非零退出。`glb_netwk_*` 不計為 driver（分配網路不是來源）。
三個 target 都是 opt-in，不在 `make test` 內。

| 掃描 | 目標數 | 覆蓋 | oracle 陽性 | model/oracle 歧異 | 執行資訊 |
|---|---:|---|---:|---:|---|
| `leds` adds-only | 49,090 | 全類別窮舉 | 14 | 0 | 16 workers、75.6 分 — **由執行 log 提取**（見下） |
| `leds` add+remove | 351 | 全類別窮舉 | 0 | 0 | 10 workers、45 秒 — 由執行 log 提取 |
| `dense` add+remove | 36,343 | 全類別窮舉 | 0 | 0 | 16 workers、107.6 分 — **JSONL summary 記錄** |

三份結果檔的 header 都記錄 `icebox.py` sha256 `5d13cbb7…` 與 IceStorm 套件版本
`0~20230218gitd20a5e9-1`；ASC sha256 分別是 leds `e982ad49…`、dense `9feba8df…`。

**來源標示**：`leds` 兩份掃描是在 oracle 加入 summary 記錄功能**之前**啟動的，其
JSONL 內只有 header 沒有 summary，因此上表的 worker 數與耗時係從執行 log 提取，
**不是掃描當下產生的記錄**，也未事後補寫進資料檔。`dense` 那份是新版本產生的，
worker 數與耗時直接來自檔內 summary 記錄。

`leds` adds-only 的 14 個陽性座標與 `exhaustive.py` 報告的 14 個**完全相同**
（雙向差集為空），且每個的衝突網路增量都恰為 +1；`make oracle-leds-report` 會把
座標完整性、唯一性、+1 增量、陽性數與零歧異一次檢查完並以退出碼表示。

**結論**：在現有 IceStorm database 與 driver whitelist 的範圍內，`leds` adds-only
的偽陰性問題**正式關閉** —— 不是抽樣，是 49,090 個全數逐一以整張圖重建獨立判定。
`dense` 的 add+remove 類亦全數判定，split-aware 分割邏輯在 36,343 個案例上與獨立
oracle 完全一致。

**仍未涵蓋**：`dense` 的 adds-only 類（203,986 個，未掃，以該 fixture 的實測速率
估計約 10 小時）；driver whitelist 以外的硬 IP 來源（PLL、oscillator），且兩個
fixture 都沒有實例化這些硬 IP，因此這條邊界目前**測不到**，需要專屬 fixture；以及
model 與 oracle 共用同一個 IceStorm database，兩者一致不能排除資料庫本身的錯誤。
矽上仍未做過任何爭用量測。

### 硬 IP：PLL fixture 與由設定推導的 driver identity（2026-08-22）

`leds` 與 `dense` 都沒有實例化任何硬 IP，因此兩者**在結構上無法**測到「來源不是
LUT／IO 輸入／RAM 讀取／DSP」的情況。`work/pll.v` + `work/pll.pcf` 是為此建立的
fixture，檢查腳本是 `work/pll_check.py`（`make pll-check`，已掛進 `make test`）。

**兩個會讓 fixture 變成空殼的陷阱**（都已避開並寫在 `pll.v` 註解裡）：

1. 接上 `LOCK` 會讓 nextpnr 報 `PLL has LOCK output, need to pass all outputs via
   LUT`，把**所有** PLL 輸出繞經 LUT，圖上的 driver 於是變成 LUT 而不是 PLL。
2. `--no-promote-globals` 會連 `PLLOUTGLOBAL` 一起拉回 fabric，global 路徑整條消失。
   正解是用 `SB_PLL40_2F_PAD`：port A 的 GLOBAL 當時脈（進 global network），
   port B 的 CORE 當**資料**（資料網路不會被提升為 global，因此留在 fabric routing）。

**發現的模型缺口**：icebox 的 `pllinfo_db["5k"]` 把 PLL 輸出配置在 IO tile
（`PLLOUT_A = (12,31) block 1`、`PLLOUT_B = (13,31) block 0`），而 `padin_pio_db`
把它們對應到 `glb_netwk_7` 與 `glb_netwk_2`。修正前：

- core 端點 `(12,31,'io_1/D_IN_0')` 被判為 `('io', …)` —— 只是名字**碰巧**命中
  `io_*/D_IN_*`，模型從未讀過 PLL 設定；
- global 端點 `(12,31,'glb_netwk_7')` 判為 `None`。該元件有 833 個 segment，
  **全部是 `lutff_global/*` 這種 sink，driver 清單是空的** —— PLL 驅動的 global
  network 在圖上是一條**沒有來源的網路**，任何把第二個來源接上去的突變都不會被
  判為衝突。這是一整類真實偽陰性，且完全落在既有兩個 fixture 的盲區。

**identity 模型**（`exhaustive.py` 與 `oracle.py` 各自獨立實作同一組物理假設）：
由 `PLLTYPE` 判斷是否啟用（`000` = DISABLED 直接略過），依 PLL 型別決定啟用哪些
port，再經 `pllinfo_db` 與 `padin_pio_db` 取得 core 與 global 兩個端點。**同一個
port 的 core 與 global 共用一個 identity**（例如 `("pll",12,31,"A")`）—— 它們是同
一個物理輸出的兩條分配路徑，拆成兩個 identity 會在兩條路徑被接在一起時產生假陽性。
PLL 佔用的 IO block **不再疊加**普通 IO identity（否則同一網路上同時出現 io 與 pll
兩個來源，一樣是假陽性）。global 端點**只在對應的 `padin_glb_netwk` extra bit 啟用
時**標註。`glb_netwk_*` 本身永遠不是 driver。

**兩個具名陽性**（model 與全圖重建 oracle 皆判定衝突，衝突網路增量皆 +1）：

| | 翻轉 | 啟用的 route | 參與的來源 |
|---|---|---|---|
| CORE | `(12,30) B12[53]` 0→1 | `lutff_6/out -> sp4_r_v_b_29` | `("lutff",12,30,6,"comb")` + `("pll",12,31,"B")` |
| GLOBAL | `(19,0) B4[15]` 0→1 | `local_g0_5 -> fabout` | `("lutff",8,29,2,"out")` + `("pll",12,31,"A")` |

GLOBAL 那個需要先把一個**目前不影響任何 route** 的 mux selector 預置起來
（`(19,0) B5[15]` 0→1）。這份測試基準由 `pll_check.py` **生成**並在生成時斷言：
啟用的 route 集合前後完全相同（+0 / −0 條），且衝突數維持 0；ASC **不是人工編輯**的，
基準檔 `pll_selector.asc` 也納入 `verify-repro` 的逐位元比對。

**負向回歸**：`PLLTYPE=000` 時不產生任何 `("pll",…)` identity；移除
`padin_glb_netwk 7` 後 global 標註消失但 core 標註仍在；`glb_netwk_2` 在本 fixture
中為 `None`（port B 未使用 GLOBAL 路徑）；同一 port 的 core／global 合併後仍只算一個
identity；PLL 佔用 block 的 `D_IN_1` 不得冒出普通 IO driver。

**覆蓋邊界（必須照這樣引用）**：已驗證的是 **UP5K `SB_PLL40_2F_PAD` 的 port A
global 與 port B core**。**未涵蓋**：port A 的 core 路徑、其餘 PLL 變體、以及
oscillator 與所有其他硬 IP。另外 IceStorm 的 `icebox_vlog` 對 PAD 型 PLL 的 port A
core 輸出使用 `io_N/PAD` 這個名稱，而本模型統一標註在 `io_N/D_IN_0`；要涵蓋該情況
需要另一個 fixture 或額外的 synthetic endpoint 建模。

## 3. Decode、readback 與獨立性

公開的 Lattice 配置流程描述寫入 configuration SRAM、啟動以及 CDONE 檢查，
沒有提供 CRAM readback 命令。因此本文採用的準確表述是「沒有公開的 CRAM
readback 流程」，而不是對未公開矽功能作絕對斷言。

主機端流程是：

```text
IceStorm map → 編輯 ASC → icebox_vlog 解碼 → gate-level/狀態測試
                                            ↓
                            經授權後：燒錄 → 觀測行為
```

`icebox_vlog` 能捕捉突變程式與解碼結果之間的不一致，例如誤翻 DffEnable。
但 map 與 decoder 都依賴 IceStorm，同一個 database 錯誤可能被兩邊共同接受；
因此 decoder 是很好的結構守門員，但不是獨立的物理 map oracle。

readback、decode 和行為驗證處理不同層次：

- flash/readback：傳輸與儲存內容；
- decode：依資料庫解釋結構；
- 行為測試：檢查被選定的可觀測結果。

三者互補，不能互相完全替代。

## 4. LUT 位元順序錯誤與修正

IceStorm 的 LC 20 個內容位不是「前 16 個 LUT、後 4 個控制」：

```python
LUT_BITNUMS = [4,14,15,5,6,16,17,7,3,13,12,2,1,11,10,0]
SEQ_BITNUMS = [8,9,18,19]
```

最初版本漏翻 LUT 16、17，並誤翻控制位 8、9，使組合輸出變成時序輸出。
目前 `iceutil.py`、`bitclass.py`、`exhaustive.py` 與 `mkprobe.py` 共用同一份
正確映射；`mkprobe.py` 還會在修改前後明確斷言 sequential bits 未改變。

## 5. Known-answer probe

baseline 的 LED pin 對應為：

| LED | pin | icebox net | counter bit |
|---|---:|---|---:|
| B | 39 | `io_4_31_0` | 25 |
| R | 40 | `io_5_31_0` | 23 |
| G | 41 | `io_6_31_0` | 24 |

### mut2：負例

翻轉 `(4,30) LC6`，使 LED_B 從 `!n26` 變成 `n26`。它只把八色循環旋轉
四格；對沒有外部時間基準的自由跑動顯示不可分辨。`mkprobe.py` 預設返回失敗，
阻止把這個 probe 當成有效燒錄候選。

### mut3：有效例

翻轉 `(5,29) LC3` 的 16 個 LUT-INIT 位，使 LED_R 從 `!n24` 變成 `n24`：

| | baseline | mut3 |
|---|---|---|
| 序列 | 黑→紅→綠→黃→藍→洋紅→青→白 | 紅→黑→黃→綠→洋紅→藍→白→青 |
| 輸出結構 | combinational assign | combinational assign |
| BIN 大小 | 104,090 B | 104,090 B |
| BIN 差異 | — | 6 bytes |

目前 testbench 直接 force 反解 netlist 的 `n24/n25/n26`，對 baseline、mut2、
mut3 各窮舉八個狀態並斷言 RGB pin 電平，不再等待 2^23 個 clock。

## 6. 板上觀測記錄

以下是先前已授權操作留下的記錄：

| # | bitstream | flash 寫入後讀回 MD5 | 預測 | 記錄的板上觀測 |
|---|---|---|---|---|
| 1 | `leds.bin` | `a4a98a593f0f2c982b051e5ae5d268c8` | baseline 循環 | 一致 |
| 2 | `leds_mut2.bin` | `0db588e57f3355a20fda7b2468119f19` | 僅相位旋轉 | 肉眼無法分離 |
| 3 | `leds_mut3.bin` | `049d0f1c38300b25974002c97710ff6c` | 紅黑、黃綠等相鄰交換 | 一致 |

`verify_*.bin` 與三個對應輸入 BIN byte-identical，支持外部 flash 寫入/讀回
一致。肉眼 LED 順序沒有影片或儀器 trace，因此應視為實驗記錄，而不是可由
目錄單獨第三方稽核的物理證據。

### 2026-08-22 無爭用重驗

本次先完成 USB 枚舉、官方電路圖、候選 driver 與恢復路徑的安全檢查。
因現場沒有電流計，且 iCELink GPIO reset 查詢不能可靠完成，沒有燒錄任何
routing multi-driver 候選；實板操作只涵蓋已通過 gate-level 測試的 baseline
與 LUT-INIT-only mut3。

| 步驟 | 寫入映像 | 104,090-byte 讀回 SHA-256 | 肉眼觀察 |
|---|---|---|---|
| 操作前備份 | `leds_mut3.bin` | `f3622e1b584c98467990ca439fc459bf22cd387c7e6e91de016333b934a15d00` | — |
| baseline 重驗 | `leds.bin` | `04c77c9d231b93df2cd63fea0167f24ad2dac04d5b3b9a16cdf3bd818ee672a5` | 黑→紅→綠→黃→藍→洋紅→青→白，符合預期 |
| mut3 重驗 | `leds_mut3.bin` | `f3622e1b584c98467990ca439fc459bf22cd387c7e6e91de016333b934a15d00` | 紅→黑→黃→綠→洋紅→藍→白→青，符合預期 |

兩次寫入後均立即讀回並以 `cmp` 做 byte-for-byte 比對。收尾時 flash 保留
操作前的 `leds_mut3.bin`；讀回檔位於 `build/physical/`。LED 序列仍是人工
觀察，沒有示波器或影片 trace，因此證據邊界與上段相同。

## 7. 可重現流程

```sh
make all
make test
make analyze
make verify-repro
```

建置使用最小化的 `work/top.pcf`，避免完整板卡 PCF 對未使用 port 產生警告。
所有新產物與日誌寫入 `build/`；上述命令不會連接或燒錄 FPGA。

## 8. 可搬到其他 FPGA family 的部分

可搬的是方法，不是 iCE40 的數字：

1. 明確區分 database coordinate、local route event、global driver candidate
   與 silicon measurement。
2. 突變後先 decode，再做結構與可觀測行為測試。
3. probe 在取得板卡時間前先通過鑑別力檢查。
4. LUT-only、受限 routing 與 raw mutation 分別量化其搜尋空間和模型內風險。

7-series 必須使用該 family 的 PIP 方向、driver 規則、frame/ECC 與 readback
能力重新建模；不能直接外推 iCE40 的比例。

## 9. 剩餘限制

- 位元普查只涵蓋 logic tile，不是 IO/RAM/DSP/IP/global configuration 全晶片普查。
- 「非全零 tile」是 ASC 資料特徵，不等同精確的設計使用性分析。
- 全域 driver graph 的來源 whitelist 是 LUT `out/lout`、IO `D_IN_*`、RAM `RDATA_*`
  及 UP5K DSP `mult/O_*`；前三類沿用 IceStorm `icebox_vlog -D` heuristic。PLL
  pad/global、振盪器與其他 hard-IP output 尚未完整做 configuration-aware identity，
  因此不能把這份 driver 集合外推成完整 UP5K 物理 driver map。
- driver graph 沒有類比電壓、強度與瞬態模型。
- 未對每個 routing event 做完整功能可達性或可觀測性分析。
- 只有一塊板，沒有跨晶片 robustness 實驗。
- 本專案是 probe 與安全分析，不是完整 evolutionary run。

因此 Claim B 的目前最穩健版本是：

> device-local map 能建立較保守、可審查且可量化的 mutation operator；
> 主機端模型可排除大量結構風險候選，但完整物理安全性仍需要獨立模型、
> 有鑑別力的行為測試，以及在必要時經授權的矽上驗證。
