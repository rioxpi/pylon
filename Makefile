CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -O3 -lutil

RELEASE_FLAGS = -static -s

AGENT_DIR = agent
SERVER_DIR = server
BUILD_DIR = build

TARGET = $(BUILD_DIR)/agent
TARGET_STATIC = $(BUILD_DIR)/agent_static
TARGET_STAGER = $(BUILD_DIR)/stager
SRC = $(AGENT_DIR)/agent.cpp
STAGER_SRC = $(AGENT_DIR)/stager.c

.PHONY: all clean agent static server stager

all: agent

agent: $(SRC)
		@mkdir -p $(BUILD_DIR)
		$(CXX) $(CXXFLAGS) $(SRC) -o $(TARGET)
		@echo "Compiled"

static:$(SRC)
		@mkdir -p $(BUILD_DIR)
		$(CXX) $(CXXFLAGS) $(RELEASE_FLAGS) $(SRC) -o $(TARGET_STATIC)
		@echo "static compiled"

server:
		cd $(SERVER_DIR) && python3 main.py
	
clean:
		rm -rf $(BUILD_DIR)
stager: $(STAGER_SRC)
		@mkdir -p $(BUILD_DIR)
		gcc -O3 -nostdlib -static -no-pie -s -fno-ident -fno-asynchronous-unwind-tables -fno-stack-protector -ffunction-sections -fdata-sections -Wl,--gc-sections $(STAGER_SRC) -o $(TARGET_STAGER)
		@echo "Compiled"