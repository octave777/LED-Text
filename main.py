import sys
import argparse
import time
import os
import json
import subprocess
import termios
import tty
import fcntl
from PIL import Image, ImageDraw, ImageFont
from colorlight_module import ColorLight5a75Controller

def get_input_interactively(prompt):
    """
    키패드 NumLock이 꺼진 상태에서도 숫자 입력을 처리할 수 있는 인터렉티브 입력 함수입니다.
    터미널의 Raw 모드를 사용하여 이스케이프 시퀀스(화살표, Home, End 등)를 직접 해석합니다.
    """
    print(prompt, end="", flush=True)
    input_str = ""
    fd = sys.stdin.fileno()
    
    # 키패드 매핑 (NumLock Off 시 발생하는 ANSI 이스케이프 시퀀스)
    keypad_map = {
        "\x1b[4~": "1", "\x1b[F": "1",    # 1 (End)
        "\x1b[B": "2",                  # 2 (Down)
        "\x1b[6~": "3",                 # 3 (PgDn)
        "\x1b[D": "4",                  # 4 (Left)
        "\x1b[G": "5", "\x1b[E": "5",   # 5 (Center/Begin)
        "\x1b[C": "6",                  # 6 (Right)
        "\x1b[1~": "7", "\x1b[H": "7",  # 7 (Home)
        "\x1b[A": "8",                  # 8 (Up)
        "\x1b[5~": "9",                 # 9 (PgUp)
        "\x1b[2~": "0",                 # 0 (Ins)
        "\x1b[3~": ".",                 # . (Del)
        "\x1b[Op": "0", "\x1b[Oq": "1", "\x1b[Or": "2", "\x1b[Os": "3",
        "\x1b[Ot": "4", "\x1b[Ou": "5", "\x1b[Ov": "6", "\x1b[Ow": "7",
        "\x1b[Ox": "8", "\x1b[Oy": "9"
    }

    while True:
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            
            # 이스케이프 시퀀스 처리 (\x1b로 시작)
            if ch == '\x1b':
                seq = ch
                # 배타적 논블로킹 모드로 전환하여 나머지 시퀀스 수집
                orig_fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, orig_fl | os.O_NONBLOCK)
                try:
                    time.sleep(0.02) # 시퀀스 문자들이 도착할 때까지 아주 짧게 대기
                    while True:
                        try:
                            next_ch = sys.stdin.read(1)
                            if not next_ch: break
                            seq += next_ch
                        except: break
                finally:
                    fcntl.fcntl(fd, fcntl.F_SETFL, orig_fl)
                
                if seq in keypad_map:
                    ch = keypad_map[seq]
                else:
                    # 매핑되지 않은 시퀀스는 무시
                    continue

            # 일반 문자 및 매핑된 키패드 문자 처리
            if ch in ('\r', '\n'): # Enter
                print()
                break
            elif ch in ('\x7f', '\x08'): # Backspace
                if input_str:
                    input_str = input_str[:-1]
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            elif ch == '\x03': # Ctrl+C
                raise KeyboardInterrupt
            elif ch.isprintable() or ch.isdigit():
                input_str += ch
                sys.stdout.write(ch)
                sys.stdout.flush()

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    return input_str

# 전역 변수로 현재 표시할 이미지
current_img = None

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
    parser.add_argument('--initial-font-size', '-ifs', type=int, default=50, help='초기 이미지 글자 크기 (기본: 50)')
    parser.add_argument('--initial-text-color', '-itc', type=str, default="white", help='초기 이미지 글자 색상 (기본: white)')
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

    # 3. 텍스트 너비 및 높이 계산 (정확한 잉크 박스 영역)
    # 더미 드로우 객체를 사용하여 텍스트의 가로 너비와 상하좌우 오프셋을 구합니다.
    temp_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]  # 텍스트의 실제 세로 잉크 높이 반영
    
    offset_x = bbox[0] # 좌측 여백
    offset_y = bbox[1] # 상단 여백 추가

    # 4. 텍스트 전용 임시 캔버스 생성 (RGBA)
    # 높이를 실제 인쇄 영역 텍스트 높이로 캔버스를 만듭니다.
    # 안전장치: 빈 문구이거나 렌더 에러로 0 이하 크기가 나온 경우 최소 1픽셀 확보
    if text_w <= 0: text_w = 1
    if text_h <= 0: text_h = 1
    
    text_canvas = Image.new('RGBA', (text_w, text_h), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_canvas)
    
    # 텍스트 그리기
    # X와 Y 오프셋을 모두 빼주어 캔버스의 (0,0) 모서리 끝단부터 꽉 차게 텍스트를 그림
    text_draw.text((-offset_x, -offset_y), text, font=font, fill=text_color)

    # 5. 최종 패널 중앙에 텍스트 캔버스 합성
    paste_x = (width - text_w) // 2
    paste_y = (height - text_h) // 2
    
    final_img.paste(text_canvas, (paste_x, paste_y), text_canvas)
    
    return final_img


# 패널 하드웨어가 마지막 프레임을 기억하므로, 변경 시에만 전송하는 방식

def main():
    global current_img
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
        # Linux용 인터페이스 확인 명령 (ifconfig -l은 BSD/macOS용임)
        if sys.platform.startswith('linux'):
            # /sys/class/net/ 아래 디렉토리 목록으로 인터페이스 리스트 확보
            available_ifaces = os.listdir('/sys/class/net/')
        else:
            # macOS 등 BSD 계열
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
    
    # 초기 이미지 생성
    current_img = create_text_image(args.text, args.width, args.height, args.initial_font_size, args.initial_text_color, args.bg_color)
    blank_img = create_text_image(args.text, args.width, args.height, args.initial_font_size, args.initial_text_color, args.bg_color)
    # 초기 이미지 전송
    controller.output_frame(blank_img)
    controller.output_frame(current_img)
    print(f"초기 이미지 전송 완료: '{args.text}'")

    try:
        print("\n새로운 텍스트를 입력하고 Enter를 누르면 화면이 즉시 바뀝니다.")
        print("종료하려면 Ctrl+C를 누르세요.")

        # 메인 스레드: 사용자 입력 처리 루프
        while True:
            new_text = get_input_interactively(f"\n[출력할 텍스트 입력]: ")
            if new_text:
                # 텍스트 가공 (마지막 3글자 유지, + 포함 시 공백)
                display_text = new_text[-3:] if len(new_text) > 3 else new_text
                if '+' in new_text:
                    display_text = "  "
                
                # 새로운 이미지 생성 (이후부터는 --font-size 등 일반 옵션 사용)
                new_img = create_text_image(display_text, args.width, args.height, args.font_size, args.text_color, args.bg_color)
                blank_img = create_text_image(" ", args.width, args.height, args.font_size, args.text_color, args.bg_color)
                current_img = new_img
                
                # 즉시 전송
                controller.output_frame(blank_img)
                controller.output_frame(new_img)
                
                print(f">> 전송 갱신됨: '{display_text}'")

    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 중단되었습니다.")
    except Exception as e:
        print(f"오류 발생: {e}")
        if "Operation not permitted" in str(e):
            print("힌트: 네트워크 로우 소켓 접근을 위해 sudo 권한이 필요할 수 있습니다.")

if __name__ == "__main__":
    main()
