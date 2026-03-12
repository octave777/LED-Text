import sys
import argparse
import threading
import time
import os
import json
import subprocess
from PIL import Image, ImageDraw, ImageFont
from colorlight_module import ColorLight5a75Controller

# 전역 변수로 현재 표시할 이미지# 공유 데이터 및 동기화 객체
current_img = None
img_lock = threading.Lock()
running = True

def load_config():
    """LED_Config 파일에서 기본 설정을 로드합니다."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "LED_Config")
    
    # 기본값 설정
    defaults = {
        "interface": "eth0",
        "width": 320,
        "height": 240,
        "color_order": "BGR",
        "font_size": 150,
        "text_color": "white",
        "bg_color": "black",
        "brightness": 100,
        "gamma": 1.0
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                defaults.update(user_config)
        except Exception as e:
            print(f"설정 파일('LED_Config') 로드 중 오류 발생 (기본값 사용): {e}")
            
    return defaults

def get_args():
    defaults = load_config()
    parser = argparse.ArgumentParser(description='Colorlight 5A-75B Modular Controller (v2)')
    
    # 필수 및 주요 옵션
    parser.add_argument('--text', '-t', type=str, default="TLS Systems", help='출력할 문자열 (기본: Hello!)')
    parser.add_argument('--interface', '-i', type=str, default=defaults["interface"], help=f'네트워크 인터페이스 (기본: {defaults["interface"]})')
    parser.add_argument('--width', '-W', type=int, default=defaults["width"], help=f'패널 가로 해상도 (기본: {defaults["width"]})')
    parser.add_argument('--height', '-H', type=int, default=defaults["height"], help=f'패널 세로 해상도 (기본: {defaults["height"]})')
    
    # 색상 및 폰트 설정
    parser.add_argument('--color-order', '-co', type=str, default=defaults["color_order"], help=f'색상 순서: RGB, BGR, GRB 등 (기본: {defaults["color_order"]})')
    parser.add_argument('--font-size', '-fs', type=int, default=defaults["font_size"], help=f'글자 크기 (기본: {defaults["font_size"]})')
    parser.add_argument('--text-color', type=str, default=defaults["text_color"], help=f'글자 색상 (기본: {defaults["text_color"]})')
    parser.add_argument('--bg-color', type=str, default=defaults["bg_color"], help=f'배경 색상 (기본: {defaults["bg_color"]})')
    
    # 추가 제어 옵션 (C++ 원본 기능 반영)
    parser.add_argument('--brightness', '-b', type=int, default=defaults["brightness"], help=f'밝기 0-100 (기본: {defaults["brightness"]})')
    parser.add_argument('--gamma', '-g', type=float, default=defaults["gamma"], help=f'감마값 (기본: {defaults["gamma"]})')
    parser.add_argument('--firmware', '-fw', type=int, default=0, help='펌웨어 버전 (13 이상이면 패킷 중복 전송 활성)')
    parser.add_argument('--fps', '-f', type=float, default=10, help='초당 프레임 수 (FPS, 기본: 10, 예: 0.1은 10초당 1프레임)')
    parser.add_argument('--count', '-c', type=int, default=0, help='전송할 총 프레임 수 (0은 무제한, 기본: 0)')
    parser.add_argument('--once', action='store_true', help='단 한 번만 전송하고 종료')

    return parser.parse_args()

def create_text_image(text, width, height, font_size, text_color, bg_color):
    """
    설정에 따라 텍스트 이미지를 생성합니다.
    문자열의 종류(g, q 등 descender 유무)와 상관없이 일관된 세로 중앙 위치를 유지하도록
    폰트의 메트릭 정보를 사용하여 이미지를 생성합니다.
    """
    # 1. 패널 배경 이미지 생성
    final_img = Image.new('RGB', (width, height), color=bg_color)
    
    # 2. 폰트 로드 시도
    font = None
    try:
        # 프로젝트 내 font 폴더의 GothicBold.ttf를 최우선으로 시도
        script_dir = os.path.dirname(os.path.abspath(__file__))
        primary_font_path = os.path.join(script_dir, "font", "GothicBold.ttf")
        
        font_paths = [
            primary_font_path,
            "/System/Library/Fonts/Cache/AppleGothic.ttf", 
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
        ]
        for path in font_paths:
            try:
                if os.path.exists(path):
                    font = ImageFont.truetype(path, font_size)
                    break
            except:
                continue
        if not font:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()

    # 3. 폰트 메트릭 정보 가져오기 (ascent: 베이스라인 위쪽, descent: 베이스라인 아래쪽)
    try:
        ascent, descent = font.getmetrics()
    except AttributeError:
        # 기본 폰트의 경우 metrics가 없을 수 있으므로 예외 처리
        ascent, descent = font_size, font_size // 4
    
    # 폰트의 전체 고정 높이 (모든 글자가 공유하는 박스 높이)
    line_height = ascent + descent

    # 4. 텍스트 너비 계산 (정확한 잉크 영역)
    # 더미 드로우 객체를 사용하여 텍스트의 가로 너비와 좌측 오프셋을 구합니다.
    temp_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    offset_x = bbox[0] # 좌측 여백

    # 5. 텍스트 전용 임시 캔버스 생성 (RGBA)
    # 높이를 line_height로 고정함으로써 문자 종류에 상관없이 일관된 높이를 확보합니다.
    text_canvas = Image.new('RGBA', (text_w, line_height), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_canvas)
    
    # 텍스트 그리기
    # y=0은 폰트의 ascent 시작점입니다. x는 bbox[0]만큼 당겨서 왼쪽 끝에 맞춥니다.
    text_draw.text((-offset_x, 0), text, font=font, fill=text_color)

    # 6. 최종 패널 중앙에 텍스트 캔버스 합성
    paste_x = (width - text_w) // 2
    paste_y = (height - line_height) // 2
    
    final_img.paste(text_canvas, (paste_x, paste_y), text_canvas)
    
    return final_img


# 패널 하드웨어가 마지막 프레임을 기억하므로, 변경 시에만 전송하는 방식

def main():
    global current_img, running
    args = get_args()
    
    print(f"--- ColorLight v2 설정 ---")
    print(f"인터페이스: {args.interface}")
    print(f"해상도: {args.width}x{args.height}")
    print(f"색상 순서: {args.color_order}")
    print(f"텍스트: '{args.text}' (크기: {args.font_size}, 색: {args.text_color})")
    print(f"--------------------------")

    # 네트워크 인터페이스 자동 선택 및 폴백 로직
    # 사용자가 지정하거나 설정파일에 있는 인터페이스를 먼저 시도하고, 
    # 해당 장치가 없을 경우 eth0 -> en5 -> enp0s6 순서로 시도합니다.
    selected_interface = args.interface
    try:
        available_ifaces = subprocess.check_output(["ifconfig", "-l"]).decode().split()
        
        # 현재 선택된 인터페이스가 존재하지 않는 경우에만 자동 탐색 시작
        if selected_interface not in available_ifaces:
            candidate_list = ["eth0", "en5", "enp0s6"]
            found = False
            for candidate in candidate_list:
                if candidate in available_ifaces:
                    print(f"알림: '{selected_interface}' 인터페이스를 찾을 수 없어 '{candidate}' 인터페이스를 자동으로 선택합니다.")
                    selected_interface = candidate
                    found = True
                    break
            
            if not found:
                print(f"경고: 기본 인터페이스 목록({candidate_list}) 중 사용 가능한 인터페이스를 찾지 못했습니다. '{args.interface}'를 그대로 시도합니다.")
    except Exception as e:
        print(f"인터페이스 확인 중 오류 발생: {e}")

    # 컨트롤러 인스턴스 생성
    controller = ColorLight5a75Controller(
        interface=selected_interface,
        width=args.width,
        height=args.height,
        color_order=args.color_order
    )
    
    # 상세 옵션 설정
    controller.set_brightness(args.brightness)
    controller.set_gamma(args.gamma)
    controller.firmware_version = args.firmware
    
    # 시작 시 Colorlight 카드 설정 감지 및 출력
    controller.detect_and_print_config()
    
    try:
        if args.once or args.count > 0:
            # 지정된 횟수만큼 전송 모드
            img = create_text_image(args.text, args.width, args.height, args.font_size, args.text_color, args.bg_color)
            
            num_frames = 1 if args.once else args.count
            print(f"프레임 {num_frames}회 전송 시작...")
            
            interval = 1.0 / args.fps if args.fps > 0 else 0.01
            for i in range(num_frames):
                controller.output_frame(img)
                if num_frames > 1 and i < num_frames - 1:
                    time.sleep(interval)
            
            print(f"총 {num_frames}개 프레임 전송 완료!")
            
        else:
            # 기본 모드: 인터랙티브 (스레딩 사용)
            print("지속적 출력 모드 활성화됨 (백그라운드에서 화면을 유지합니다)")
            print("새로운 텍스트를 입력하고 Enter를 누르면 화면이 즉시 바뀝니다.")
            print("종료하려면 Ctrl+C를 누르세요.")
            
            # 초기 이미지 생성 및 즉시 전송
            img = create_text_image(args.text, args.width, args.height, 50, args.text_color, args.bg_color)
            controller.output_frame(img)
            print("초기 화면 전송 완료.")
            
            current_text = args.text
            while True:
                # 새로운 입력 대기 (Blocking)
                print(f"\n현재 표시 중: '{current_text}'")
                new_text = input("출력할 새로운 텍스트 입력: ")
                
                if new_text:
                    # 새로 입력된 문자열로 완전히 교체
                    current_text = new_text
                    
                    # 항상 새로 입력된 문자열의 마지막 3글자만 유지
                    if len(current_text) > 3:
                        display_text = current_text[-3:]
                    else:
                        display_text = current_text
                    
                    # '+' 기호가 포함되어 있는지 검사 (새 입력 전체 기준)
                    if '+' in current_text:
                        display_text = " "  # 공백 출력

                    # 새로운 이미지 생성 후 즉시 전송
                    new_img = create_text_image(display_text, args.width, args.height, args.font_size, args.text_color, args.bg_color)
                    controller.output_frame(new_img)
                    print(f"텍스트가 '{display_text}'(으)로 갱신 및 전송되었습니다.")
                else:
                    print("입력이 없어 이전 상태를 유지합니다.")

    except KeyboardInterrupt:
        running = False
        print("\n사용자에 의해 프로그램이 중단되었습니다.")
    except Exception as e:
        running = False
        print(f"오류 발생: {e}")
        if "Operation not permitted" in str(e):
            print("힌트: 네트워크 로우 소켓 접근을 위해 sudo 권한이 필요할 수 있습니다.")

if __name__ == "__main__":
    main()
