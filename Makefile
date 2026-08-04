# -----------------------------
# Makefile for SDL2 + SDL2_ttf + SDL2_image Project (macOS Homebrew)
# Requires: brew install sdl2 sdl2_ttf sdl2_image
# -----------------------------

# Compiler
CXX := g++

# Directories
SRC_DIR := src
INC_DIR := include
BUILD_DIR := build

# Executable
TARGET := $(BUILD_DIR)/app

# Find all .cpp files in src/
SRCS := $(wildcard $(SRC_DIR)/*.cpp)

# Object files will go in build/
OBJS := $(patsubst $(SRC_DIR)/%.cpp,$(BUILD_DIR)/%.o,$(SRCS))

# Homebrew path (Apple Silicon default)
BREW_PREFIX := /opt/homebrew

# SDL2_image headers (brew: sdl2_image). Prefer pkg-config when available.
SDL2_IMAGE_CFLAGS := $(shell pkg-config --cflags SDL2_image 2>/dev/null)
ifeq ($(SDL2_IMAGE_CFLAGS),)
SDL2_IMAGE_CFLAGS := -I$(BREW_PREFIX)/opt/sdl2_image/include/SDL2
endif

# Compiler flags
CXXFLAGS := -std=c++17 -Wall -Wextra -I$(INC_DIR) -MMD -MP \
            $(shell sdl2-config --cflags) \
            -I$(BREW_PREFIX)/include/SDL2 \
            $(SDL2_IMAGE_CFLAGS) \
            $(SDL2_MIXER_CFLAGS)

# Linker flags (SDL2_image libs from pkg-config when available)
SDL2_IMAGE_LDFLAGS := $(shell pkg-config --libs SDL2_image 2>/dev/null)
ifeq ($(SDL2_IMAGE_LDFLAGS),)
SDL2_IMAGE_LDFLAGS := -L$(BREW_PREFIX)/opt/sdl2_image/lib -lSDL2_image
endif

SDL2_MIXER_CFLAGS := $(shell pkg-config --cflags SDL2_mixer 2>/dev/null)
ifeq ($(SDL2_MIXER_CFLAGS),)
SDL2_MIXER_CFLAGS := -I$(BREW_PREFIX)/opt/sdl2_mixer/include/SDL2
endif

SDL2_MIXER_LDFLAGS := $(shell pkg-config --libs SDL2_mixer 2>/dev/null)
ifeq ($(SDL2_MIXER_LDFLAGS),)
SDL2_MIXER_LDFLAGS := -L$(BREW_PREFIX)/opt/sdl2_mixer/lib -lSDL2_mixer
endif
# Only link SDL2_mixer when the library is actually installed.
SDL2_MIXER_AVAILABLE := $(shell test -f $(BREW_PREFIX)/opt/sdl2_mixer/lib/libSDL2_mixer.dylib -o -f $(BREW_PREFIX)/opt/sdl2_mixer/lib/libSDL2_mixer.so && echo yes)

LDFLAGS := $(shell sdl2-config --libs) \
           -L$(BREW_PREFIX)/lib -lSDL2_ttf \
           $(SDL2_IMAGE_LDFLAGS)
ifeq ($(SDL2_MIXER_AVAILABLE),yes)
LDFLAGS += $(SDL2_MIXER_LDFLAGS)
CXXFLAGS += -DUSE_SDL2_MIXER=1
endif

# -----------------------------
# Default target
# -----------------------------
all: $(TARGET)

# Link object files into the final executable
$(TARGET): $(OBJS) | $(BUILD_DIR)
	$(CXX) $(OBJS) $(LDFLAGS) -o $@

# Compile .cpp files to .o files and generate dependency files (.d)
$(BUILD_DIR)/%.o: $(SRC_DIR)/%.cpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Include dependency files if they exist
-include $(OBJS:.o=.d)

# Ensure build directory exists
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

# Clean up
clean:
	rm -rf $(BUILD_DIR)/*.o $(BUILD_DIR)/*.d $(TARGET)

# Run the app
run: $(TARGET)
	./$(TARGET)

# Regenerate map script opcode list for Python editor (FEATURE-MAP-044 / FEATURE-MAP-048: scans src/op.cpp)
regen-event-ops:
	python3 tools/extract_map_script_ops.py

.PHONY: all clean run regen-event-ops test test-script-runtime test-game-state

# C++ unit tests (no SDL) — Phase 4 runtime smoke
TEST_SCRIPT_RUNTIME := $(BUILD_DIR)/test_script_runtime
TEST_GAME_STATE := $(BUILD_DIR)/test_game_state

test: test-script-runtime test-game-state

test-script-runtime: $(TEST_SCRIPT_RUNTIME)
	./$(TEST_SCRIPT_RUNTIME)

test-game-state: $(TEST_GAME_STATE)
	./$(TEST_GAME_STATE)

$(TEST_SCRIPT_RUNTIME): tests/test_script_runtime.cpp src/script_engine.cpp src/op.cpp | $(BUILD_DIR)
	$(CXX) -std=c++17 -Wall -Wextra -I$(INC_DIR) $^ -o $@

$(TEST_GAME_STATE): tests/test_game_state.cpp src/game_state.cpp | $(BUILD_DIR)
	$(CXX) -std=c++17 -Wall -Wextra -I$(INC_DIR) $^ -o $@
