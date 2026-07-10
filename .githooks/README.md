# .githooks — 病人姓名外洩防線

本 repo 是**公開**的：檔案內容、commit 訊息，任何人未登入都讀得到。
`.gitignore` 只能擋「整個檔案不上傳」，擋不住「必須公開的檔案裡出現姓名」——
2026-07-10 就是這樣把一位患者的名字寫進 `config.js` 的註解裡，並在 18 個 commit 訊息中留下真名↔pid 對照。

## 啟用（重新 clone 後必做一次）

```bash
git config core.hooksPath .githooks
```

設了之後 `.git/hooks/` 會被忽略，一切以本目錄為準。

## 三道關

| Hook | 時機 | 掃什麼 |
| :--- | :--- | :--- |
| `pre-commit` | commit 前 | staged 的檔案內容（順便沿用原本的 `?v=` 快取版本號 bump） |
| `commit-msg` | 寫完訊息後 | commit 訊息本身（`pre-commit` 看不到訊息，必須另一道） |
| `pre-push` | 推送前 | 整棵樹 ＋ 所有待推 commit 的訊息 |

`pre-push` 是最後一道，存在的理由是前兩道可能被 `--no-verify` 或 `--amend` 繞過，
錯誤已經躺在本機歷史裡；**push 才是不可逆的那一步**。

## 名單怎麼來

`privacy_scan.py` 在執行時才從 `names.local.js` / `history.local.js`（皆 gitignore、只在本機）
抽出姓名，並產生變體：

- 原樣全名
- **三字中文名去姓**（`顏OO` → `OO`）— 2026-07-10 的漏網之魚正是這一類
- 英文名小寫

所以**本目錄的任何檔案都不含姓名**，可以安全公開。

## 已知極限（別當成保證）

- `git commit --no-verify` / `git push --no-verify` 會整個跳過，擋不住蓄意繞過。
- 還沒登錄進 `names.local.js` / `history.local.js` 的新病人，抓不到。
- **pid 本身就是名字**（英文暱稱那兩個）只會印警告、不阻擋，否則每次 commit 都被卡住。
  要根治得換 pid，但那等於換鎖，患者手上的 `?who=` 連結會失效、必須重發。
- 名單檔不存在時（例如新 clone 還沒放個資檔）會**放行並印警告**——此時防線是關的。
