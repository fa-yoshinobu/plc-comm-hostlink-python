# Pr_HOST-LINK-COMMUNICATION-FUNCTION

KEYENCE KV-XLE02 Host Link 通信ライブラリ（Python）です。

## 構成

- `hostlink/`: ライブラリ本体
- `docs/host_link_protocol.md`: マニュアル整理資料

## クイックスタート

```python
from hostlink import HostLinkClient

with HostLinkClient("192.168.0.10", transport="tcp") as plc:
    plc.change_mode("RUN")
    value = plc.read("DM200.S")
    plc.write("DM200.S", 1234)
    values = plc.read_consecutive("R100", 4)
```
