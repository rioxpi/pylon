CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -O3 -lutil

RELEASE_FLAGS = -static -s

AGENT_DIR = agent
SERVER_DIR = server
BUILD_DIR = build

TARGET = $(BUILD_DIR)/agent
TARGET_STATIC = $(BUILD_DIR)/agent_static
SRC = $(AGENT_DIR)/agent.cpp

.PHONY: all clean agent static server

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
		python3 $(SERVER_DIR)/main.py
	
clean:
		rm -rf $(BUILD_DIR)