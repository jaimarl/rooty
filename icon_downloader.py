import os
import urllib.request

ICONS = [
    "message-square",
    "brain-circuit",
    "venetian-mask",
    "audio-lines",
    "user",
    "workflow",
    "palette",
    "chevron-left",
    "send-horizontal"
]
os.makedirs("gui/assets/icons", exist_ok=True)

for icon in ICONS:
    url = f"https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{icon}.svg"
    urllib.request.urlretrieve(url, f"ui/assets/icons/{icon}.svg")
    print(f"✅ Скачано: {icon}.svg")
