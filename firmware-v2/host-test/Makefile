# Хостовые тесты модуля maze (без HAL).
#   make test   — собрать и запустить
#   make clean  — убрать бинарник
#
# Компилятор: любой cc (clang/gcc). Модуль maze.c берётся прямо из прошивки,
# чтобы тестировался тот же код, что попадает в микроконтроллер.
# Для maze.c включены строгие предупреждения (как для прошивки),
# для самого теста — обычные.

CC       ?= cc
CFLAGS   ?= -std=c99 -O1 -g -Wall -Wextra -fsanitize=address,undefined
STRICT    = -Wpedantic -Wshadow -Wconversion -Wsign-conversion -Werror
INC       = -I../Core/Inc
BIN       = test_maze

.PHONY: test build clean

test: build
	./$(BIN)

build: $(BIN)

maze.o: ../Core/Src/maze.c ../Core/Inc/maze.h
	$(CC) $(CFLAGS) $(STRICT) $(INC) -c ../Core/Src/maze.c -o maze.o

$(BIN): test_maze.c maze.o ../Core/Inc/maze.h
	$(CC) $(CFLAGS) $(INC) test_maze.c maze.o -o $(BIN)

clean:
	rm -f $(BIN) maze.o
	rm -rf $(BIN).dSYM
