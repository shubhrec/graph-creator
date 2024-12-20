const serviceB = require('./serviceB');

class ServiceA {
    process() {
        return serviceB.handle('from A');
    }
}

module.exports = new ServiceA();