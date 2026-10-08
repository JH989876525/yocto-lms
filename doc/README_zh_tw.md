# yocto-lms — Yocto 本地鏡像伺服器 (Local Mirror Server)

[English](../README.md)

為本機的 Yocto 建置提供共用的 `DL_DIR` / `SSTATE_DIR`:每個 release 各一組
downloads + sstate-cache、單一共用的 `git2/` 鏡像目錄,以及清理過期 sstate 物件的工具。

`lms` 是一個 shell function(`lms.sh`),負責選擇 release 並匯出
`DL_DIR` / `SSTATE_DIR`,主要搭配 `kas-container` 建置使用。

## Layout

```
<lms>/                      本 README 所在的目錄
├── lms.sh                  `lms` 與 `kas-container` shell function
├── tools/
│   └── sstate-prune.py     sstate 清理工具
├── git2/                   共用的 bitbake git 鏡像
├── scarthgap/
│   ├── downloads/          git2 -> ../git2
│   ├── sstate-cache/
│   └── git2 -> ../git2
├── wrynose/                與 scarthgap/ 相同
├── sstate-prune.list       清理候選清單(自動產生,已被 git 忽略)
└── doc/                    README_zh_tw.md
```

`.gitignore` 會排除各 release 目錄與 `git2/`(快取資料)以及自動產生的 `*.list`。

## Prerequisites

- bash、python3
- `kas-container`(僅容器建置需要)
- 磁碟空間:快取很大,可用 `lms status` 查看用量與剩餘空間。

## Quick start

```bash
echo 'source <lms>/lms.sh' >> ~/.bashrc    # 然後開啟新的 shell

lms 6            # 選擇 wrynose(5 = scarthgap);建立並匯出 DL_DIR 與 SSTATE_DIR
lms status       # 所選 release 的大小與剩餘磁碟空間
kas-container build ...                     # 照常建置
```

`kas-container` 會將 `DL_DIR` 與 `SSTATE_DIR` 傳入容器。

設定(環境變數):

| 變數 | 預設值 | 用途 |
|---|---|---|
| `LMS_HOME` | `lms.sh` 所在目錄 | 快取目錄結構的根目錄 |
| `LMS_STAMPS_GLOB` | `/mnt/2026/*/build*/tmp*/stamps` | `prune` 搜尋建置 stamps 的位置 |
| `LMS_STAMPS` | 自動偵測 | 以冒號分隔的 stamps 目錄;優先於 glob |

## Workflow

### 1. 選擇 release

```bash
lms 5            # scarthgap
lms 6            # wrynose
```

### 2. 清理 sstate-cache

符合以下任一條件的 sstate 物件會被保留:

1. 其 hash 被目前某個建置的 stamps 參照,
2. 在 `--days` 天內被存取過(預設 14),
3. 屬於同一 recipe/arch/task 中最新的 `--keep-newest` 個(預設 5)。

其餘皆為清理候選。`prune` 在主機上執行,並自動偵測所有符合
`LMS_STAMPS_GLOB` 的建置之 stamps。

| 選項 | 說明 |
|---|---|
| `--apply` | 實際刪除(預設為 dry-run) |
| `--days N` | 保留 N 天內存取過的物件 |
| `--keep-newest N` | 每個 recipe/arch/task 保留最新的 N 個 |
| `--min-free GiB` | 剩餘空間足夠時不做任何事 |

```bash
lms prune                              # dry-run,寫出 <lms>/sstate-prune.list
lms prune --days 30 --keep-newest 10   # 較保守的 dry-run
lms prune --min-free 500               # 僅在剩餘空間低於 500 GiB 時才清理
lms prune --apply                      # 刪除候選物件
lms prune --days 7 --min-free 300 --apply
LMS_STAMPS=/work/a/build/tmp/stamps:/work/b/build/tmp/stamps lms prune   # 指定 stamps 目錄
```

執行 `--apply` 之前,務必先檢查 `sstate-prune.list`。`prune` 只處理 sstate,
downloads 不會被自動清理。

### 3. 新增 release

```bash
mkdir -p <lms>/<rel>/{downloads,sstate-cache}
ln -s ../git2 <lms>/<rel>/downloads/git2
ln -s ../git2 <lms>/<rel>/git2
```

接著在 `lms.sh` 的 `case` 中加入該 release。

## 共用的 git2/

`git2/`(bitbake 的 bare git 鏡像,占 downloads 的大宗)透過相對符號連結由所有
release 共用;`downloads/` 下的其他內容仍依 release 各自保存。

- **kas-container** 只掛載 `DL_DIR`(為 `/downloads`),所以連結在容器內會解析為
  `/git2`。`lms.sh` 中的 `kas-container` function 會加上 `-v <lms>/git2:/git2`;
  若直接呼叫 `/usr/bin/kas-container`(腳本、cron)會繞過它,連結將失效。
- **還原**:`rm <rel>/downloads/git2 && cp -a <lms>/git2 <rel>/downloads/git2`
- `<rel>/downloads/git2.old` 是一次性合併留下的舊副本,確認建置正常後即可刪除。
