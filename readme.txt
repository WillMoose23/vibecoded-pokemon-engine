Compile and Run Command

clang++ test.cpp -o app $(sdl2-config --cflags --libs);./app

# Build the project
make

# Run the compiled app
make run

# Clean build files
make clean

# Open everything in kate
open -a Kate include/*.h src/*.cpp src/*.json readme.txt
