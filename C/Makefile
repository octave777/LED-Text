CXX = g++
CXXFLAGS = -O3 -Wall -std=c++11
LDFLAGS = -lm

TARGET = colorlight_led
SRCS = main.cpp ColorLightController.cpp TextRenderer.cpp
OBJS = $(SRCS:.cpp=.o)

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)
	@echo "------------------------------------------------"
	@echo "빌드 완료: $(TARGET)"
	@echo "sudo 없이 실행하려면 다음 명령을 한 번 실행하세요:"
	@echo "sudo setcap cap_net_raw+ep $(TARGET)"
	@echo "------------------------------------------------"

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET)

setup: $(TARGET)
	sudo setcap cap_net_raw+ep $(TARGET)
	@echo "권한 설정 완료. 이제 ./$(TARGET) 으로 바로 실행 가능합니다."

.PHONY: all clean setup
