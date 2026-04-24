# Excel BI 看板（最小可用版）

这个项目实现了你要的核心功能：

1. 导入 Excel；
2. 写入本地 SQLite 数据库；
3. 在指定时间范围内，统计某一列各内容出现次数；
4. 生成扇形统计图（Pie Chart）。

## 运行方式

在项目目录执行：

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

启动后在浏览器打开 Streamlit 页面，按以下步骤：

1. 左侧上传 `xlsx/xls` 文件并选择工作表；
2. 点击“导入到数据库”；
3. 选择“统计列”和“时间列”；
4. 选择时间范围，系统自动生成扇形图和统计表。

## 数据库

- 数据库文件：`bi_dashboard.db`
- 当前导入策略：每次导入会覆盖 `records` 表（`replace`）

后续如果你需要“保留历史导入批次”，可以升级为：
- 增加 `import_batch_id`；
- 每次 append 导入；
- 看板按批次/时间切换。
