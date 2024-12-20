const timestamp = () => new Date().toISOString();

function log(message) {
    console.log(`[${timestamp()}] ${message}`);
}

module.exports = { log };