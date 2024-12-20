const mathUtils = require('../utils/mathUtils');
const stringUtils = require('../utils/stringUtils');
const external = require('../../lib/external');

class APIService {
    constructor() {
        this.baseURL = 'https://api.example.com';
    }

    formatResponse(data) {
        const result = mathUtils.add(data.value, 10);
        const formatted = stringUtils.format('%s: %s', data.key, result);
        return external.process(formatted);
    }
}

module.exports = new APIService();