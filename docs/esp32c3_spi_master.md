# 用 ESP32-C3 當外部 SPI master 直灌 iCE40 SRAM（接線方案，尚未接線）

日期：2026-08-22　狀態：**紙上方案，硬體尚未接線、韌體尚未撰寫**

動機：iCESugar 原廠 iCELink 只提供 flash 路徑，實測 `icesprog -w` 一次 6.5 s；
若走 slave-SPI 直灌 CRAM，15 MHz 下純傳輸約 55 ms（104,090 B），約 100×。
這是 CoBEA 那篇 130× 的同一條路（他們用 FT2232H + HX8K breakout）。

## 依據

- iCESugar v1.5 原理圖 —— 上游倉庫 [github.com/wuxx/icesugar](https://github.com/wuxx/icesugar)
  的 `schematic/iCESugar-v1.5.pdf`
- 板子：YD-ESP32-C3（原生 USB JTAG/serial，USB ID `303a:1001`）
- Lattice iCE40 Programming and Configuration（slave SPI 流程）

> **裝置節點是當時本機的枚舉結果，不是可重現的路徑。** 撰寫當下 ESP32-C3 枚舉為
> `/dev/ttyACM1`、iCELink CDC 為 `/dev/ttyACM0`；`ttyACMn` 的編號隨插拔順序改變，
> 請依 USB ID 自行判定，不要照抄。

## 關鍵事實（原理圖確認）

FPGA 的四支配置腳沒有引到任何排針，但與 flash U5 同網路：

```
U5 W25Q64 (SOIC-8)              iCE40UP5K
  1 CS   = ICE_SS      ───────── pin16 SPI_SS    (R24 10K 上拉 → 預設高 = master boot)
  6 CLK  = ICE_SCK     ───────── pin15 SPI_SCK
  5 SI   = FLASH_MOSI  ──J3───── pin17 SPI_SI
  2 SO   = FLASH_MISO  ──J3───── pin14 SPI_SO
  4 GND
CRESET_B ── FPGA pin8，R3 10K 上拉，**S2 按鈕直接短到 GND**
CDONE    ── FPGA pin7，R5 2.2K 上拉，D1 藍燈（亮 = 配置完成）
```

`J3` 是 2×2 模式跳線，絲印 `"=" Prog Flash ‖ Prog ICE`：
- `=` 橫接（1-4、2-3，**交叉**）= FPGA 當 master 從 flash 開機 ← 出廠/目前狀態
- `‖` 直接（1-2、4-3）= 外部 SPI master 直通 FPGA `SPI_SI` ← **本方案要切到這裡**

J3 腳位：1=FLASH_MOSI（左上）、2=ICE_MOSI（左下）、4=ICE_MISO（右上）、3=FLASH_MISO（右下）。

## 接線表

| ESP32-C3 | 方向 | iCESugar 接點 | 訊號 | 方式 |
|---|---|---|---|---|
| GPIO6 (FSPICLK) | → | U5 pin 6 | SCK | SOIC-8 夾 |
| GPIO7 (FSPID) | → | U5 pin 5 | SPI_SI（經 J3 1-2）| SOIC-8 夾 |
| GPIO10 | → | U5 pin 1 | SPI_SS（整段拉低）| SOIC-8 夾 |
| GND | — | U5 pin 4 | GND | SOIC-8 夾 |
| GPIO5 | → 開汲極 | S2 焊盤（非接地側）| CRESET_B | 飛線 |
| GPIO4 | ← 輸入 | R5 下端 / D1 陽極 | CDONE | 飛線（可選）|

一顆 SOIC-8 測試夾一次拿到 SPI 三線 + GND，**零焊接**；只有 CRESET_B 需要焊。

避開的腳：GPIO2/8/9 是 strapping、GPIO18/19 是原生 USB（使用中）、GPIO20/21 是 UART0。
GPIO6/7/10 是 C3 的 IO_MUX FSPI 腳（可到 80 MHz；iCE40 配置時脈上限 25 MHz，取 15~20 MHz）。
兩邊都是 3.3V，不需要準位轉換。

## 三個安全依據

1. **CRESET_B 必須開汲極**（只拉低，高電位交給 R3 10K）。STM32 也在這條線上，
   但 S2 按鈕本來就是直接把這條線短到 GND，所以拉低有原廠設計背書。
2. **SS 全程拉低 → flash 只解析到一個無效 opcode**。SPI flash 在 CS 下降沿後只把
   第一個 byte 當指令；整份 bitstream 在單一 CS-low 視窗內送完，第一個 byte 是
   `0xFF`（非法），其餘全被忽略到 CS 拉高，不會誤觸發抹除/寫入。
3. **ESP32 驅動匯流排時不要跑 icesprog**。ICE_SS/ICE_SCK/FLASH_MOSI 是 STM32、
   flash、FPGA 三方共用。反推依據：FPGA 開機時必須自己當 master 讀 flash，所以
   iCELink 韌體在 flash transaction 之外必定把這些腳釋放成高阻（協定裡有
   `CMD_FLASH_TRANSACTION_START/END` 一對），否則 FPGA 根本開不了機。

## 配置時序（slave SPI）

1. CRESET_B 拉低、SS 拉低
2. 等 ≥200 ns
3. 放開 CRESET_B（經 10K 上拉；開汲極的上升時間約 µs 級）
4. 等 **≥1.2 ms**（UP5K 清 CRAM，比 HX 的 800 µs 長；實作抓 2 ms）
5. 8 個 dummy clock（SS 仍低）
6. 送 bitstream，MSB first，SPI mode 0 或 3
7. 再打 ~100 個 clock，同時看 CDONE 拉高
8. SS 拉高

## 注意事項

- 配置完成後 pin 14/15/16/17 變回一般 user I/O → **`.pcf` 永遠不要指派這四支**，
  且配置結束後把 C3 的 SCK/MOSI/SS 設回輸入。
- J3 切到 `‖`（或拔掉）之後 FPGA 不會自己從 flash 開機，上電是空的等灌。
  切回 `=` 即恢復原廠行為。
- 走線 <10 cm；SCK 若有振鈴串一顆 33 Ω。
- bitstream 傳到 C3 的路徑：原生 USB CDC 全速約 0.2~0.4 s / 104 KB。要壓到最短
  就照 CoBEA 的做法把 base bitstream 放在 C3 的 flash，之後只送差異。
