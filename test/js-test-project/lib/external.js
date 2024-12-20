const helpers = require('./helpers');

class External {
    process(data) {
        return helpers.helper2(data);
    }
}

module.exports = new External();