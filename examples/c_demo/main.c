#include <stdio.h>

struct Point {
    int x;
    int y;
};

int add(int a, int b) {
    return a + b;
}

int main() {
    int result = add(10, 20);
    return 0;
}
