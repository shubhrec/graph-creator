const external = require('./external');

function helper1(data) {
    return `Helper 1: ${data}`;
}

function helper2(data) {
    return `Helper 2: ${JSON.stringify(data)}`;
}

module.exports = {
    helper1,
    helper2
};