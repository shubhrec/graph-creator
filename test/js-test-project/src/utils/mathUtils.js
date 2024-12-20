// Regular function declarations
function add(a, b) {
    return a + b;
}

function multiply(x, y) {
    return x * y;
}

function divide(a, b) {
    if (b === 0) throw new Error('Division by zero');
    return a / b;
}

module.exports = {
    add,
    multiply,
    divide
};