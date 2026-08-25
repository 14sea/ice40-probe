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
這些 sweep target 都是 opt-in，不在 `make test` 內。

| 掃描 | 目標數 | 覆蓋 | oracle 陽性 | model/oracle 歧異 | 執行資訊 |
|---|---:|---|---:|---:|---|
| `leds` adds-only | 49,090 | 全類別窮舉 | 14 | 0 | 16 workers、86.2 分 |
| `leds` add+remove | 351 | 全類別窮舉 | 0 | 0 | 4 workers、3.2 分 |
| `dense` add+remove | 36,343 | 全類別窮舉 | 0 | 0 | 16 workers、159.2 分 |
| **`dense` adds-only** | **203,986** | **全類別窮舉** | **2,471** | **0** | **16 workers、880.2 分** |
| **合計** | **289,770** | — | **2,485** | **0** | — |

**「合計 289,770」是「fixture × 類別」的案例數，不是唯一物理座標數。** `leds` 與
`dense` 的座標有 45,605 個重疊，四份合併後的**唯一座標是 244,165 個**。

（2026-08-23：三份較早的結果檔曾被一次 `rm -rf build` 誤刪，已全部重跑，數字與原始一致；
輸出目錄因此改為不受 clean 影響的 `results/`。上表耗時為重跑後的實測值。）

三份結果檔的 header 都記錄 `icebox.py` sha256 `5d13cbb7…` 與 IceStorm 套件版本
`0~20230218gitd20a5e9-1`；ASC sha256 分別是 leds `e982ad49…`、dense `9feba8df…`。

**來源標示**：四份結果檔**現在都含 summary 記錄**（早期兩份 `leds` 掃描在 summary
功能加入前啟動、當時只有 header，但那兩份已於 2026-08-23 重跑），上表的 worker 數與
耗時全部直接取自檔內 summary。

**模型版本標示（重要）**：四份**不是**由同一個原始碼版本產生的。`dense` adds-only
使用目前 HEAD 的 hash；`dense` add+remove 與 `leds` add+remove 使用較早版本；`leds`
adds-only 使用更早版本。各次實際的 `oracle.py`／`exhaustive.py` sha256 都誠實記錄在
各自的 header 與 `docs/evidence_manifest.md` 中。期間的差異是後來加入的 SPRAM 與
oscillator identity，而 `leds`／`dense` 都不含硬 IP（兩者的 `spram_sources` 與
`oscillator_sources` 實測皆為空集合），因此該變更對這兩個 fixture 是可證明的 no-op，
沿用舊結果在技術上成立。**但這是「經 no-op 變更分析後承接的證據」，不是「四份都由
當前 hash 直接產生」** —— 要主張後者必須重跑較早三份。

`leds` adds-only 的 14 個陽性座標與 `exhaustive.py` 報告的 14 個**完全相同**
（雙向差集為空），且每個的衝突網路增量都恰為 +1；`make oracle-leds-report` 會把
座標完整性、唯一性、+1 增量、陽性數與零歧異一次檢查完並以退出碼表示。

**結論**：在現有 IceStorm database 與 driver whitelist 的範圍內，`leds` adds-only
的偽陰性問題**正式關閉** —— 不是抽樣，是 49,090 個全數逐一以整張圖重建獨立判定。
`dense` 的 add+remove 類亦全數判定，split-aware 分割邏輯在 36,343 個案例上與獨立
oracle 完全一致。

**`dense` 的 adds-only 類也已全掃完畢（2026-08-23）**：203,986 個座標逐一以整張圖
重建獨立判定，oracle 陽性 **2,471 個，與模型預測完全相同**，零歧異。至此**這四個
類別全部完成窮舉交叉驗證**，合計 289,770 個案例（244,165 個唯一座標）、2,485 個
陽性、**0 次歧異**。

**「四個類別」指的是本專案定義的四組 sweep，不是整顆 UP5K 的設定空間。**
`oracle.py` 的列舉條件只涵蓋：非全零 logic tile、至少新增一條 routing path 的翻轉、
且分為 adds-only 與 add+remove 兩類。**不涵蓋** removal-only 的翻轉、非 routing 座標、
全零 logic tile，以及 logic tile 以外的 tile 類型。

**「偽陰性已關閉」的正確範圍**：指增量模型相對於**全圖重建**沒有偽陰性，且是在同一份
database 與同一組 driver identity 假設之下。**不能外推成「矽上沒有偽陰性」。**

**仍未涵蓋**：driver whitelist 以外的硬 IP —— **LEDDA 尚未建模**（它的啟用狀態不是
configuration 事實）；**RGBA 沒有 fabric 輸出，因此不適用於 driver graph**（不是「尚未
建模」，見盤點一節）。PLL、oscillator、I2C 與 SPI 已有專屬 fixture，見上文，但覆蓋仍是
部分的。**更根本的是**：model 與 oracle 共用
同一個 IceStorm database，兩者一致**只代表內部結構一致，不能排除資料庫本身的錯誤**。
（此處原本引「`CLKHF_DIV` 完全不進 ASC」當作資料庫缺口的例子 —— **那個說法已於
2026-08-23 撤回**，該除頻值就編碼在 `dsp1_tile (0,16)`，錯的是我當初的 tile 列舉，
不是資料庫；見後文「⚠ 2026-08-23 撤回的錯誤結論」。）矽上從未做過任何爭用量測。

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

### 硬 IP：SPRAM fixture（2026-08-22）

第二個硬 IP fixture，`work/spram.v` + `work/spram.pcf`，檢查腳本 `work/spram_check.py`
（`make spram-check`，已掛進 `make test`）。

**缺口與 PLL global 同型**：UP5K 單埠 RAM 的讀取資料是經由 ipcon tile 的
`slf_op_*` 段落離開硬 IP 的。這個名稱在**沒有硬 IP 的設計裡完全不存在**（`leds`
的圖中一個都沒有），因此以 `lutff_*/out`、`io_*/D_IN_*`、`ram/RDATA_*`、`mult/O_*`
為基礎的 whitelist 從來比對不到它 —— 16 個 `DATAOUT` 端點全部是無 driver 的網路，
任何把第二個來源接上去的突變都不會被判為衝突。

**布局是量出來的，不是假設的**（分別放 1 顆與 4 顆 `SB_SPRAM256KA` 對照）：

| 實例數 | 被設起的 `IpConfig` | 有 `slf_op` 的 ipcon tiles |
|---|---|---|
| 1 | `(0,1) CBIT_0` | `(0,1)`、`(0,2)`，各 8 個 = `DATAOUT[15:0]` |
| 4 | `(0,1)` 與 `(25,1)` 的 `CBIT_0`+`CBIT_1` | `(0,1)–(0,4)` 與 `(25,1)–(25,4)`，各 8 個 |

即每個 ipcon column 有兩顆實例：`CBIT_0` 啟用佔用 rows 1–2 的那顆，`CBIT_1` 啟用
佔用 rows 3–4 的那顆。identity 由設定推導，**每個輸出位元各自一個 identity**
（`("spram", x, y, index)`）—— 與 PLL 的 port 不同，`DATAOUT` 的各位元是彼此獨立的
物理驅動源，若被接在一起本來就是爭用，所以這裡**不做** aliasing。

**具名陽性**（model 與全圖重建 oracle 皆判定，增量 +1）：

| 翻轉 | 啟用的 route | 參與的來源 |
|---|---|---|
| `(1,1) B1[48]` 0→1 | `lutff_0/out -> sp4_v_b_16` | `("lutff",1,1,0,"comb")` + `("spram",0,2,7)` |

**負向回歸**：清掉 `CBIT_0` 後所有 `("spram",…)` identity 消失；未啟用實例的
rows 3–4 不帶 identity；`leds` 設計零 SPRAM identity 且圖中完全沒有 `slf_op` 段落；
停用 bank 上的 `slf_op` 解析為 `None`。

**覆蓋邊界**：只驗過 **ipcon column 0 的一顆 `SB_SPRAM256KA`，且僅讀取資料路徑**。
未涵蓋：寫入路徑、同 column 的第二顆、右側 column、以及 oscillator 與其餘所有硬 IP。

### 硬 IP：振盪器 fixture（2026-08-23）

第三個硬 IP fixture，`work/osc.v` + `work/osc.pcf`，檢查腳本 `work/osc_check.py`
（`make osc-check`，已掛進 `make test`）。

**缺口與 PLL global 完全同型**：HFOSC 與 LFOSC 都是在圖上沒有自己來源段落的情況下
餵進 `glb_netwk_*`。修正前兩條全域網路（832 與 830 個 segment，全是 `lutff_global`
sink）**都沒有 driver**，任何接上第二個來源的突變都不會被判為衝突。

**兩件事是量出來的，不是假設的**：

1. **哪個 padin 索引屬於哪顆振盪器** —— 只放 HFOSC 會設 `padin_glb_netwk 4`，只放
   LFOSC 會設 `5`。沒有沿用 icebox 原始碼裡那條註解，因為它標的是另一顆晶片的表。
2. **`padin_glb_netwk` extra bit 代表來源在片上** —— 拿 padin 4 共用的那支實體接腳
   （package pin 23）當全域時脈輸入時，**完全不設任何 extra bit**，而且該 pad 自己的
   `io_0/D_IN_0` 會進入元件並被正確判為 driver。所以 pad 驅動與硬 IP 驅動是可分辨的，
   模型也只標註**有證據的兩個索引**，其餘一律不碰；PLL 已擁有的全域會被跳過。

**具名陽性**（model 與全圖重建 oracle 皆判定，增量 +1）：

| 翻轉 | 啟用的 route | 參與的來源 |
|---|---|---|
| `(12,31) B4[15]` 0→1 | `local_g1_4 -> fabout` | `("lutff",5,28,0,"comb")` + `("hfosc",19,31)` |

需先預置 `(12,31)` 的 `B5[14]`、`B5[15]`；該基準由腳本生成並斷言 route 集合 +0/−0、
衝突數維持 0。fixture 另含一個 `OSC_CONFLICT_PROBE` 輸出腳，唯一目的是讓某個 LUT
輸出落到 `(12,31)` 的 local net 上 —— 沒有它，那顆 fabout mux 的八個來源全都沒有
driver，這個陽性就構造不出來。

**覆蓋邊界（必須照這樣引用）**：只驗過 **HFOSC**。LFOSC 的全域對應的 `fabout` 位於
io tile `(12,0)`，而 **sg48 封裝沒有把該 tile 的任何 block 接出來**，因此無法把 LUT
輸出帶到那顆 mux，也就構造不出第二個來源 —— 這是封裝限制，不是模型缺陷。I2C 已於
2026-08-25 建立 identity，SPI 同日跟進（皆見下文）；LEDDA 仍未建模，RGBA 無 fabric
輸出、不適用於 driver graph。

**⚠ 一項已撤回的錯誤結論**：本文件先前寫過「`CLKHF_DIV` 在 ASC 裡完全沒有表示」。
**那是錯的。** 它編碼在 **`dsp1_tile (0,16)` 的兩個 IpConfig 位元**（`CBIT_3` = 低位
`B2[7]`、`CBIT_4` = 高位 `B5[7]`），四個除頻值一一對應，`osc_check.py` 現在會直接
斷言它。當初測錯的原因很有教訓價值：那次比對列舉了 io／logic／ipcon／ramb／ramt
五種 tile，**漏掉了 `dsp_tiles`** —— 而那正是唯一有變化的 tile。這與本專案稍早
「全域檢查被錯誤地包在 `if local_dual_route` 內」是同一種失效：**不完整的列舉會產出
看起來乾淨的否定結論**。`work/osc_evidence.py` 現在會重建全部四個除頻值並釘住編碼。

**工程對策（不只是修這一個 bug）**：所有腳本不再手寫 tile 類型清單，改用
`iceutil.configuration_tiles` 這個 canonical iterator；`assert_tile_coverage`
會在 `iceconfig` 出現任何**未被分類**的 tile collection 時直接失敗（必須明確納入
迭代，或以理由具名列入 `NON_TILE_CONFIGURATION`）。`make tile-coverage` 另外釘住
那個具體回歸：canonical 列舉找得到 `dsp_tiles[1] (0,16) B5[7]` 這個除頻位元，而
**舊的手寫清單找不到** —— 失敗案例被刻意保留在測試裡，因為一個從未被觸發過的
守衛什麼也證明不了。

### 硬 IP 盤點與 carry-out identity（2026-08-24）

在寫任何新 identity 之前先做的普查步驟，`work/hard_ip_inventory.py`
（`make hard-ip-inventory`）。判定一律要求不只一個獨立觀察。

| 硬 IP | 放置 | fabric 端點（`slf_op`） | 啟用位元 | 判定 |
|---|---|---|---|---|
| `SB_I2C` | X0/Y31 | **15** @ (0,29),(0,30) | `I2C_ENABLE_0/1` @ (13,31)/(12,31) | 值得建 fixture → **已建，見下文（2026-08-25）** |
| `SB_SPI` | X0/Y0 | **25** @ (0,19)–(0,22) | `SPI_ENABLE_0..3` @ (7,0)/(6,0) | 值得建 fixture → **已建，見下文（2026-08-25）** |
| `SB_LEDDA_IP` | X0/Y31 | **4** @ (0,28),(0,29) | **無** | 值得建 fixture；啟用狀態**未判定** |
| `SB_RGBA_DRV` | X0/Y30 | **0** | `RGBA_DRV_EN` @ (0,28) `CBIT_5` | **不適用於 driver graph** → 負向回歸已建（2026-08-25） |

**權威來源是 `icebox.extra_cells_db['5k']`，不是我們合成出來的設計。** 這份 db 直接
給出每個硬 IP 的 port→segment 對應與啟用位元座標；合成設計的角色是**驗證這份 db**，
而不是取代它。

**⚠ 一個已修正的數字**：本盤點最初報告 SPI 有 **19** 個 fabric 端點。**那是錯的**
—— 19 是我那份 Verilog 的性質，不是元件的性質：它只接了 `MCSNO0`/`MCSNOE0`，
漏掉 `MCSNO1..3` 與 `MCSNOE1..3`，於是 `(0,21)` 的三個與 `(0,22)` 的三個端點從未被
placer 觸及。量到的集合是 db 的**真子集**（無多餘項），正確數字是 **25**。這是本專案
第三次踩到同一種失效：**不完整的列舉產出一個看起來像結論的數字**。對策同前 ——
驗收改為與 db 的端點集合做**雙向**比對，而不是比對「端點落在哪些 tile」（後者少一半
也會通過）。

**啟用位元是從編出來的設計讀回來的**，而且每一個都附一個負向對照：同一位元在
**沒有**該硬 IP 的設計（`leds.asc`）中必須讀到 `0`。少了這個對照，「位元是 1」可能
只是因為它恆為 1。

**LEDDA 標為未判定，而非「無條件啟用」**：公開設定裡它**沒有任何啟用位元**，所以
無法從 configuration 判斷它是否在驅動 fabric。這是關於矽的問題，本盤點回答不了；
在拿到判定之前不替它建立 identity。另注意 **I2C 與 LEDDA 共用 ipcon tile (0,29)**，
而 `CLKHF_FABRIC` 又落在 LEDDA 所在的 (0,28) —— **ownership 必須解析 `slf_op` 索引，
永遠不能按 tile 歸屬**。

**`lutff_N/cout` identity（`make carry-check`）**：`cout` 是 logic cell 的第二個實體
輸出，原本的 driver pattern 只比對 `out`/`lout`，因此漏掉。它**必須以 CarryEnable
（seq bit 0）為閘門**：`cout -> in_3` 是可程式化路由，突變可以把 carry 關閉的 cell 的
`cout` 段落拉進圖中，無條件的 regex 會**憑空發明一個 driver**。

加上它**不改變任何結果，而且可證明**，證明是逐一數出來的，不是抽查：

| 性質 | 值 |
|---|---|
| 檢查的 logic tile | 660 |
| `cout` 作為 routing 來源的次數 | 4,620（每個 tile 恰好 7，無例外） |
| `cout` 作為 routing 目的端 | 0 |
| `in_3` 作為 routing 來源 | 0 |
| `in_3` mux 總數 | 5,280（每 tile 8） |
| 來源數不等於 16 的 mux | 0 |
| 位元群組不一致的 mux | 0 |
| 可同時成立的來源 pair | 0 |

所以**含 `cout` 的網路不可能含第二個來源** —— 要求「`cout` 參與的具名多來源案例」是
無法滿足的，因為這種案例不存在且證明不可能存在。`make carry-check` 釘的是這個結構
論證本身。

**回歸的驗收方式也一併修正**：先前它只讀封存的 JSONL 數出 14／2,471，那**不構成
「陽性集合不變」**——即使當前模型把每個陽性都搬到別的座標，這種檢查照樣通過。現在
它用當前模型**重算**陽性座標，與封存的掃描結果做**雙向差集**，兩個方向都必須是空的。

### 振盪器的第二個輸出：fabric 直出端點（2026-08-24）

`extra_cells_db` 揭露 HFOSC 與 LFOSC 各有**兩個**輸出：全域網路，以及一條直接進入
fabric 的段落 —— **`CLKHF_FABRIC` = `(0,28,'slf_op_7')`**、**`CLKLF_FABRIC` =
`(25,29,'slf_op_0')`**。模型原本只標註了全域那條，於是任何把訊號接到 fabric 端點所在
網路上的突變，都會看到一個**沒有來源**的網路 —— 與 PLL global 完全同型的偽陰性。

**nextpnr 從不選這條路徑**（即使把振盪器輸出當資料用，甚至加 `--no-promote-globals`，
它仍然一律 promote 成全域），所以合成設計永遠測不到它。但 IceStorm 資料庫裡
`slf_op_7 -> span` 的 routing entry **確實存在**，單一位元翻轉就能啟用。模型評估的是
翻轉，不是 place-and-route 工具會產生的設計。

兩條端點**與各自的全域路徑共用同一個 identity**（同一顆振盪器的兩條路徑；拆開會在
兩路徑相遇處產生假陽性），這與 PLL 的 core/global 處理一致。座標一律由 db 推導，
不寫死在腳本裡。

**第二個具名陽性**（model 與全圖重建 oracle 皆判定，增量 +1）：

| 翻轉 | 啟用的 route | 參與的來源 |
|---|---|---|
| `(0,28) B15[52]` 0→1 | `slf_op_7 -> sp4_r_v_b_15` | `("lutff",1,27,5,"comb")` + `("hfosc",19,31)` |

需先預置 `(1,27) B11[51]`。**與其他 selector 基準不同**，這個預置**確實會啟用一條
route**（`lutff_5/out -> sp4_v_b_26`）：fixture 裡沒有任何東西驅動 fabric 端點所能
到達的目的端，driver 必須被放上去。因此這裡斷言的不是「route 集合 +0/−0」，而是
**新增的 route 恰好等於那一條**、且衝突數仍為 0。

**閘門與覆蓋邊界**：閘門仍是 `padin_glb_netwk` 位元，它說的是「振盪器在驅動它的全域
網路」——一個**路由**事實。振盪器是否**在運轉**根本不是 configuration 事實：
`CLKHFPU`／`CLKHFEN` 是 fabric 輸入而非設定位元，沒有任何位元組合能回答它。因此
「啟用了振盪器但只用 fabric 輸出」的設計落在本標註之外；nextpnr 產不出這種設計，
所以該情況記為**未判定**，而不是被排除。

### 硬 IP：I2C identity（2026-08-25）

盤點之後的第一個 fixture（`work/i2c.v`／`work/i2c_check.py`，`make i2c-check`，已進
`make test` 與 `verify-repro`）。缺口與 SPRAM 同型：每個 `SB_I2C` 有 **15 個輸出**經
ipcon tile 的 `slf_op_*` 進入 fabric，而 `lutff_*/out`／`io_*/D_IN_*`／`ram/RDATA_*`／
`mult/O_*` 這組 whitelist 一個都比對不到 —— 於是 I2C 的每一條輸出網路都是「沒有來源」
的網路，任何把第二個 driver 接上去的突變都不會被判為衝突。

**兩個 instance 都放**，因為它們在設定上不對稱：左邊 instance 的兩個啟用位元分屬
**兩個** IO tile（`(13,31)` 的 `cbit2usealt_in_0` 與 `(12,31)` 的 `cbit2usealt_in_1`），
右邊的兩個都在 `(19,31)`。只放一個 instance 的 fixture 會漏掉一半的佈局 —— 正是把 SPI
數成 19 個端點的那種失效。選哪一個 instance 不是靠放置約束，而是靠 `BUS_ADDR74`：
`"0b0001"` 只能是 i2c_0，`"0b0011"` 只能是 i2c_1。

**量到的，不是假設的**：

* 端點與啟用位元一律取自 `icebox.extra_cells_db`，合成設計只用來**驗證**那份 db；
  驗收是與 db 的端點集合做**雙向**比對（30 個，兩個方向差集皆空）。
* 啟用位元在編出來的設計裡是 `1`，在 `leds.asc` 裡是 `0`。少了後半，「位元是 1」也
  可能只代表它恆為 1。
* **不管 SCLI/SDAI 來自專用腳位還是 fabric 暫存器，nextpnr 都會把兩個位元一起設起來**
  （兩種設計各建一次比對過）。所以這兩個位元標記的是「這個 instance 被啟用」，
  不是「專用腳位被 mux 到 IP」。本 fixture 刻意用 fabric 暫存器驅動 SCLI/SDAI，讓這
  兩件事在證據裡不會混在一起。

**identity 粒度**：每個輸出 port 各自一個 identity（`("i2c", x, y, port)`），30 個端點
30 個相異 identity —— 它們是 15 個相異的實體輸出，不是同一個來源的多條路徑（PLL 的
core/global 才是後者）。

**ownership 一律解析 port，永不按 tile**：`(0,29)` 同時載著 I2C 的七個輸出與 LEDDA 的
`LEDDON`（`slf_op_0`）；`(25,29)` 同時載著右邊 I2C 的七個輸出與 **LFOSC 的 fabric 直出
端點**（同樣是 `slf_op_0`）。按 tile 歸屬會把兩者都判給 I2C。這件事有專門的回歸：那兩個
`slf_op_0` 不在 I2C 的來源集合裡，而在振盪器 fixture 裡 `(25,29,slf_op_0)` 確實屬於
`("lfosc", 6, 31)`。模型另外在建圖時直接對 PLL／SPRAM／振盪器做端點交集檢查，有重疊就
`RuntimeError`，不讓「先查到誰算誰」悄悄決定歸屬。

**兩個具名陽性**（每個 instance 一個；model 與全圖重建 oracle 皆判定，增量 +1）：

| 翻轉 | 啟用的 route | 參與的來源 |
|---|---|---|
| `(0,30) B1[52]` 0→1 | `slf_op_0 -> sp4_r_v_b_1` | `("i2c",0,31,"SBDATO2")` + `("lutff",15,30,4,"out")` |
| `(25,29) B3[48]` 0→1 | `slf_op_1 -> sp4_v_b_18` | `("i2c",25,31,"SDAO")` + `("lutff",15,30,0,"out")` |

與振盪器 fabric 端點不同，這兩個**都不需要預先生成 selector 基準**：fixture 本身已經把
LUT 輸出送到這些 mux 能到達的 span 上，第二個來源本來就在那裡。

**具名兩個不夠，所以整個類別都窮舉了**：在四個 I2C 輸出 tile 裡，「單一位元 0→1、恰好
新增一條 route、不移除任何 route、且來源是 I2C 端點」的翻轉，模型判為衝突的共 **23 個**
（`(0,29)` 1、`(0,30)` 12、`(25,29)` 2、`(25,30)` 8），**全圖重建 oracle 逐一確認，
每一個都是 +1，零歧異**；兩個具名陽性都在這個集合裡。抽兩個樣本沒有檢定力，這個類別
小到可以窮舉，就窮舉。**未涵蓋的方向**：同樣那些 tile 裡模型判為「乾淨」的翻轉沒有被
oracle 全掃（本專案的 sweep machinery 只走 logic tile），所以這裡關掉的是偽陽性方向，
不是偽陰性方向。

**反事實有真的跑**：把 `exhaustive.i2c_driver_state` 換掉、只抽掉 `(0,30,slf_op_0)`
這一個端點的 identity、重建整張圖，同一個翻轉就被判為乾淨；其餘 29 個端點的 identity
不受影響。斷言「identity 存在」不能證明它就是決定判決的東西。

**未判定的部分，明講不猜，而且不准它變成判決**：兩個 `I2C_ENABLE` 位元**個別**代表
什麼，公開資料沒有說，這個 fixture 也回答不了（nextpnr 永遠成對寫入）。因此「恰好只設
一個」的設定由 `i2c_undetermined()` 報成 **UNDETERMINED**，並且**不給 identity**：
當成啟用會憑空發明 15 個 driver，當成停用會藏起 15 個 driver。

**⚠ 只「報告」是不夠的（2026-08-25 覆核抓到的漏洞）**：第一版把 undetermined 記下來
之後照樣建圖、照樣回答，於是那 15 個 driver 只是安靜地不在圖裡，baseline 依舊是乾淨的
0 —— **「未知」在判決層被算成「安全」**。現在 `GlobalDriverGraph` 建構與
`oracle.conflicting_nets()` 遇到 mixed state 都直接 `RuntimeError`，**拒絕給出判決**。
兩邊各有回歸，且用「把守衛拿掉就必須變紅」驗過有牙齒；另有鑑別性對照：**兩個位元都清
＝off 是有答案的狀態，判決層照常運作**。這種設定不可能由 nextpnr 產生，而且兩個位元都在
**IO tile**，落在本專案所有 sweep 的 logic-tile 範圍之外，所以沒有任何 sweep 碰得到。

**歸屬守衛也補了鑑別力測試**：`GlobalDriverGraph` 對「兩個硬 IP 宣稱同一段落」會拋
`RuntimeError`，但沒有任何 fixture 會同時啟用 I2C 與另一個重疊來源 —— 守衛從未被觸發過，
拿掉它照樣全綠。現在在**振盪器 fixture**（LFOSC 啟用、擁有 `(25,29,slf_op_0)`）上**注入**
一個 I2C 對同一段落的宣稱，釘住它必須拋出；同時斷言未注入時該 fixture 建得起來，
確保紅的是注入而不是 fixture 本身。

**另外釘住端點真的有進圖**：annotation 是從 db 推導的，拿 db 比對 db 不可能發現「某個
輸出後來沒被繞線」。因此另外斷言 db 的 30 個端點**全部出現在 `ic.group_segments()`**
裡 —— 少了這條，未來某個輸出被最佳化掉會讓 fixture 悄悄變空殼。

**順帶的效能修正（不改任何結果）**：`oracle.conflicting_nets()` 原本對**每一個 segment**
重新推導一次 PLL 以外的硬 IP 狀態；設定在走訪圖的過程中並不會改變，因此改成每次呼叫
只推導一次。答案逐位元相同，`check-analysis` 的七個釘死數字與封存掃描的雙向差集回歸
都不受影響（`leds`／`dense` 不含任何硬 IP，I2C identity 對它們是可證明的 no-op）。

**覆蓋邊界（照這樣引用）**：只涵蓋兩個 `SB_I2C` instance 的 **15 個 fabric 輸出**，
閘門是 db 指名的那組啟用位元。IP 的輸入、暫存器語意、以及單一啟用位元的意義都在邊界
之外。**SPI 已於同日建模（見下一節）；LEDDA 尚未建模（沒有啟用位元，不是 configuration
事實）；RGBA 無 fabric 輸出，故不適用於 driver graph。**

### 硬 IP：SPI identity（2026-08-25）

盤點四步的第 2 步（`work/spi.v`／`work/spi_check.py`／`work/spi_evidence.py`，
`make spi-check`、`make spi-evidence`，兩者都已進 `make test` 與 `verify-repro`）。
缺口與 SPRAM／I2C 同型：每個 `SB_SPI` 有 **25 個輸出**經 ipcon tile 的 `slf_op_*`
進入 fabric，whitelist 一個都比對不到。

**25，不是 19。** 盤點第一版量到 19，因為那份 Verilog 只接 `MCSNO0`/`MCSNOE0`，
`(0,21)`／`(0,22)` 的六個端點從未被 place —— 那是**測試平台的性質，不是元件的性質**。
本 fixture 每個 instance 的 25 個輸出全部被消費，並且與 db 做**雙向**比對；另外斷言
**50 個端點全部出現在 `ic.group_segments()`** 裡（拿 db 比 db 抓不到「輸出後來沒被繞線」）。

**兩件事改成可重生證據，不再是從 log 手抄的說法**（`work/spi_evidence.py`，16 次
build，約 10 秒）：

1. **`BUS_ADDR74` 的合法值與 instance 對應**：`SB_SPI` 不是靠放置約束選 instance，
   而是 nextpnr 讀這個參數。**全部 16 個 4-bit 值都建一次**，結果由 placer 自己的報告
   解析：只有 `0b0000` → `X0/Y0/spi_0`、`0b0010` → `X25/Y0/spi_1` 被接受。
   **被拒絕在哪一階段也一起釘住**（覆核意見）：另外 14 個**全部 synthesis 成功**、
   **全部由 nextpnr 非零退出**、**錯誤訊息都是 `Invalid value for BUS_ADDR74`**。
   只數存活者的話，就算它們其實早一步倒在 yosys，這份文件照樣會宣稱「placer 拒絕了
   它們」—— 兩者是不同的主張。
2. **「啟用」的位元向量是量出來的**：每個 instance 單獨建一次，讀回自己的四個位元＝
   `1111`、另一個 instance 的四個＝`0000`，而完全沒有 SPI 的設計八個位元全是 `0`。
   少了後兩項對照，「位元是 1」也可能只是它恆為 1。

**啟用位元的佈局兩個 instance 不同**：左邊 `SPI_ENABLE_0/1` 在 `(7,0)`、`2/3` 在
`(6,0)`；右邊 `0/2` 在 `(23,0)`、`1/3` 在 `(24,0)`。所以 fixture 兩個 instance 都放。

**identity 粒度：每個 port 一個**（50 端點／50 個相異 identity）。這次有一個**只有
per-port 粒度才抓得到的具名陽性**：同一個 instance 的兩個輸出被接到同一條網路上。

**三個具名陽性**（model 與全圖重建 oracle 皆 +1）：

| 翻轉 | 啟用的 route | 參與的來源 |
|---|---|---|
| `(0,19) B6[51]` | `slf_op_3 -> sp12_v_b_6` | `("spi",0,0,"SBDATO2")` + `("lutff",12,1,1,"out")` |
| `(25,19) B3[48]` | `slf_op_1 -> sp4_v_b_18` | `("spi",25,0,"SBDATO0")` + `("lutff",12,1,3,"out")` |
| `(0,19) B3[53]` | `slf_op_1 -> sp4_r_v_b_35` | `("spi",0,0,"SBDATO0")` + `("spi",0,0,"MCSNOE1")` |

第三個附**粒度反事實**：把 identity 折成「每個 instance 一個」再跑同一個翻轉，衝突就
消失了 —— 證明 per-port 粒度確實是判決的依據，而不只是好看的命名。另有端點反事實：
只抽掉 `(0,19,slf_op_3)` 一個端點的 identity，第一個陽性就被判為乾淨，其餘 49 個不受影響。

**這次不先用 model 篩，而是先獨立列出完整結構候選集**（覆核意見）：在八個 SPI 輸出
tile 裡，凡是「單一位元翻轉會新增或移除至少一條**碰到 SPI 端點**的 route」的座標，
全部列出 —— **601 個**（550 個純新增、50 個純移除、1 個 add+remove）。接著**同一批
候選同時跑 model 與全圖重建 oracle**：

| 類別 | 數量 | model 判衝突 | oracle 增量 |
|---|---:|---:|---|
| 全部結構候選 | 601 | 50 | 50 個 +1，551 個 0 |

**零歧異，而且兩個方向都檢查了** —— 先用 model 陽性篩選的話，模型自己判為乾淨的那
551 個永遠不會被檢定（本專案的偽陰性都是這個形狀）。16 workers 約 2 分鐘。

**⚠ 母集合本身也不能是共用假設（覆核意見）**：第一版用 model 的 `tile_model()` 列出
601 個座標，再把同一批交給兩邊 —— 那麼「列舉」就成了雙方共用的前提，**等量替換座標
仍會全綠**（只釘 601 與 550/50/1 三個數字擋不住）。現在用 **oracle 自己的
`tile_routing_entries()` 重新列舉一次**，兩份做**雙向集合比對**，而且連每個翻轉
**新增／移除哪些 route 的正規化 signature** 都比。實測：601 vs 601、雙向差集空、
signature 全同。拿掉一個座標或改掉一條 route 都會讓對應的檢查變紅（實測過）。

**結構事實（順帶釘住）**：SPI 端點在 routing 表裡**只當來源，從不當目的端**
（648 次作為來源、0 次作為目的端）。

**undetermined 一樣是 fail-closed**：四個 `SPI_ENABLE` 位元個別的語意沒有公開資料可
判定（nextpnr 永遠四個一起寫）。清掉 1、2、3 個位元三種情況都各有回歸，斷言 model 與
oracle 都報 undetermined、都不給 identity、而且**都拒絕給出判決**；對照組是「四個全清
＝off」，判決層照常運作。這些位元同樣都在 IO tile，sweep 碰不到。

**歸屬守衛改成通用的兩兩比對，而且 model 與 oracle 各有一套**：原本只拿 I2C 去對其他
三個 source map，現在 PLL／SPRAM／oscillator／I2C／SPI 五者**每一對**都比。
**⚠ 覆核抓到：這道守衛原本只存在於 model**，而 oracle 的 `driver_identity()` 是**按固定
查詢順序**取第一個命中的硬 IP map —— 重疊時它會安靜地選一個，於是交叉驗證等於繼承了
model 的守衛而不是印證它。實測（把守衛拿掉後注入重疊宣稱）**oracle 確實安靜回傳 0**。
現在 `oracle.conflicting_nets()` 自己做兩兩交集檢查，並用**同一個 LFOSC 注入案例**
（`(25,29,slf_op_0)`）釘住它必須拒絕，撤回注入後又能正常計數。

**覆蓋邊界（照這樣引用）**：只涵蓋兩個 `SB_SPI` instance 的 **25 個 fabric 輸出**，
閘門是 db 指名的那組啟用位元。IP 的輸入、暫存器語意、單一啟用位元的意義都在邊界之外。
另外一項限縮：I2C 那邊「啟用位元標記的是 instance 而不是 pad mux」有**專用腳位與 fabric
暫存器兩種設計**各建一次作為證據；**SPI 的證據只用了 fabric 暫存器**，所以 SPI 這一點是
沿用 I2C 的結果，不是自己量到的。
LEDDA 已盤點但啟用狀態不是 configuration 事實，未建模；RGBA 無 fabric 輸出、不適用。

### 硬 IP：RGBA 的負向回歸（2026-08-25）

盤點四步的第 3 步（`work/rgba.v`／`work/rgba_check.py`，`make rgba-check`，已進
`make test` 與 `verify-repro`）。**這一步刻意不建 identity** —— `SB_RGBA_DRV` 沒有任何
進入 fabric 的輸出，它驅動三支封裝腳、讀五個 fabric 輸入，是 sink 加 pin driver。
所以它是**不適用於 driver graph**，不是「尚未建模」。

**否定結論的價值等於它背後列舉的完整度**，而本專案已經三次栽在不完整的列舉上，所以
這份回歸不只是報告「找不到 `slf_op`」：

1. **28 個 db port 全部分類，且分類必須窮盡**：5 個 fabric 輸入（`CURREN`、`RGBLEDEN`、
   `RGB0/1/2PWM`，全是 `lutff_*/in_*`）、3 支封裝腳（`RGB0/1/2`）、20 個設定位元，
   **fabric 輸出 0 個**。出現任何無法歸類的 port 形狀就直接失敗，不會被略過。
2. **同一套端點抽取拿去問別的 block**：I2C 15、SPI 25、LEDDA 4、RGBA 0；放置後的設計
   也一樣（i2c 30、spi 50、rgba 0）。**一個壞掉的搜尋對前三個也會回 0**，這一條就是
   用來排除「0 來自壞掉的量測」。
3. **block 必須真的存在且真的啟用**，否則否定是空的：`RGBA_DRV_EN`（`(0,28) CBIT_5`）
   從編出來的 bitstream 讀回是 `1`、在 `leds.asc` 是 `0`；`CURRENT_MODE` 與
   `RGB0_CURRENT` 也讀得回來（六個位元恰好一個為 1）。
4. **三支腳確實是它自己的 pad**：db 的 `(4,31,0)/(5,31,0)/(6,31,0)` 經
   `pinloc_db['5k-sg48']` 對應到封裝腳 **39/40/41**；nextpnr 三次明說
   `not creating SB_IO`；在 fixture 裡那三個 tile **只剩 `glb_netwk_4`**（同樣三個 tile
   在把腳位當普通 IO 用的 `leds` 裡有 19 個 segment、含 `io_0/D_OUT_0`）。
5. **模型不是對 pad 一律視而不見**：同一個設計裡的時脈輸入腳 `(12,31) io_1/D_IN_0`
   **確實**拿到 `("io",12,31,...)` identity —— 所以 RGBA 三支腳的「沉默」是那些 pad 的
   性質，不是模型看不見 IO。
6. 整個 fixture 的 driver 種類只有 `{lutff, io}`，沒有任何硬 IP identity；model 與
   oracle 的 baseline 衝突數皆為 0。

**「不適用」與「未判定」是兩件事，這裡並排釘住**：RGBA **有啟用位元、沒有 fabric 輸出**
→ 它的狀態是 configuration 事實，而且沒有東西可驅動，是**確定的否定**；LEDDA 正好相反，
**有 4 個 fabric 輸出、沒有任何啟用位元** → 無法從 configuration 判斷它是否在驅動，
維持 **UNDETERMINED**、不建 identity。

**鑑別力（實測過）**：給 RGBA 的 port 表塞進一個假的 `slf_op` 輸出 → 四條檢查同時變紅；
把端點抽取改成永遠回空 → I2C/SPI/LEDDA 那三條立刻變紅，也就是說「RGBA 是 0」這個結論
不可能由一個壞掉的搜尋矇混過關。

**覆蓋邊界**：這說的是**公開設定裡** `SB_RGBA_DRV` 沒有進入 fabric 的路徑，因此在這張圖
裡不可能是來源。它不涉及該 block 的類比行為，而且仍是關於 IceStorm 資料庫的陳述 ——
本專案沒有任何一項在矽上量測過。

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
- 全域 driver graph 的來源 whitelist 是 LUT `out/lout/cout`、IO `D_IN_*`、RAM
  `RDATA_*` 及 UP5K DSP `mult/O_*`；前三類沿用 IceStorm `icebox_vlog -D` heuristic。
  PLL（core/global）、SPRAM、振盪器（全域與 fabric 兩條輸出）、I2C（兩個 instance 各
  15 個 fabric 輸出）與 SPI（兩個 instance 各 25 個）已有 configuration-aware identity；
  **LEDDA 已完成盤點但尚未建模**，RGBA 判定為不適用。因此仍不能把這份 driver 集合外推
  成完整 UP5K 物理 driver map。
- 振盪器 identity 的閘門是「它在驅動全域網路」這個路由事實，不是「它在運轉」——
  後者由 fabric 輸入 `CLKHFPU`／`CLKHFEN` 決定，不存在對應的設定位元。
- LEDDA 在公開設定裡沒有任何啟用位元，其啟用狀態**未判定**，因此未建立 identity。
- I2C 的兩個 `I2C_ENABLE`、SPI 的四個 `SPI_ENABLE` 位元**個別的語意皆未判定**：
  nextpnr 一律整組同時寫入，公開資料也沒有把它們分開。因此「只設其中一部分」的設定被
  明確報成 undetermined，不當成啟用（會憑空發明 15／25 個 driver），也不當成停用
  （會藏起同樣多的 driver），而且**model 與 oracle 都直接拒絕對這種設定給出判決**。
- driver graph 沒有類比電壓、強度與瞬態模型。
- 未對每個 routing event 做完整功能可達性或可觀測性分析。
- 只有一塊板，沒有跨晶片 robustness 實驗。
- 本專案是 probe 與安全分析，不是完整 evolutionary run。

因此 Claim B 的目前最穩健版本是：

> device-local map 能建立較保守、可審查且可量化的 mutation operator；
> 主機端模型可排除大量結構風險候選，但完整物理安全性仍需要獨立模型、
> 有鑑別力的行為測試，以及在必要時經授權的矽上驗證。
