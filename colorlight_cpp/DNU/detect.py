from scapy.all import conf, sendp, sniff, Raw

# 설정
interface = 'en5'  # 맥북은 보통 eth0 대신 en0, en1 등을 사용합니다.
dst_mac = "11:22:33:44:55:66"
src_mac = "22:22:33:44:55:66"
eth_type = 0x0700  # 정수형으로 입력 (Ethernet Type)

# 페이로드 준비
payload = b'\x00' * 270
payload2 = b'\x00\x00\x01' + b'\x00' * 267

# 1. 첫 번째 패킷 전송 (L2 프레임 구성)
# Scapy는 MAC 주소를 문자열 형태로 받으며, 자동으로 이더넷 헤더를 붙여줍니다.
pkt1 = Raw(load=payload)
# 실제 전송 (Ether 헤더를 직접 구성하여 전송)
from scapy.layers.l2 import Ether
frame1 = Ether(dst=dst_mac, src=src_mac, type=eth_type) / pkt1
sendp(frame1, iface=interface, verbose=False)

# 2. 패킷 수신 (sniff 사용)
# ETH_P_ALL과 유사하게 모든 패킷을 보되, 특정 조건의 패킷 하나만 캡처
print(f"Listening on {interface}...")
packets = sniff(iface=interface, count=10, timeout=2)

if packets:
    data = bytes(packets[0])
    # 리눅스 코드의 인덱스 로직을 그대로 유지 (Ethernet 헤더 14바이트 포함 상태)
    if len(data) > 13 and data[12] == 8 and data[13] == 5:
        print("Detected a Colorlight card...")
        if data[14] == 4:
            version = f"{data[15]}.{data[16]}"
            res_x = data[34] * 256 + data[35]
            res_y = data[36] * 256 + data[37]
            print(f"Colorlight 5A {version} on {interface}")
            print(f"Resolution X: {res_x} Y: {res_y}")

# 3. 두 번째 패킷 전송
frame2 = Ether(dst=dst_mac, src=src_mac, type=eth_type) / Raw(load=payload2)
sendp(frame2, iface=interface, verbose=False)