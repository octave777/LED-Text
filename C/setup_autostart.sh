#!/bin/bash

# LED Text C++ Controller Autostart Setup for .bashrc

APP_NAME="colorlight_led"
INSTALL_DIR=$(pwd)
APP_PATH="$INSTALL_DIR/$APP_NAME"
BASHRC="$HOME/.bashrc"

echo "--- $APP_NAME .bashrc 자동 실행 설정 시작 ---"

# 1. 빌드 확인
if [ ! -f "$APP_PATH" ]; then
    echo "애플리케이션이 빌드되지 않았습니다. 빌드를 먼저 수행합니다."
    make -C "$INSTALL_DIR"
fi

# 2. Sudo 없이 실행 가능하도록 권한 설정
echo "Raw Socket 권한 설정 (sudo 필요)..."
sudo setcap cap_net_raw+ep "$APP_PATH"

# 3. .bashrc에 실행 구문 추가 (중복 방지)
AUTOSTART_CMD="
# ColorLight LED Text Controller Autostart (TTY1 only)
if [ \"\$(tty)\" = \"/dev/tty1\" ]; then
    cd $INSTALL_DIR
    ./$APP_NAME
fi"

if grep -q "$APP_NAME" "$BASHRC"; then
    echo ".bashrc에 이미 설정이 존재합니다. 기존 설정을 유지하거나 수동으로 수정하세요."
else
    echo "가장 끝에 자동 실행 구문을 추가합니다..."
    echo "$AUTOSTART_CMD" >> "$BASHRC"
    echo "설정이 완료되었습니다."
fi

echo "------------------------------------------------"
echo "이제 라즈베리파이를 재부팅하거나 다시 로그인하면"
echo "TTY1(메인 화면)에서 자동으로 프로그램이 실행됩니다."
echo "------------------------------------------------"
