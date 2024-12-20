// Class with method definitions
class ArrayUtils {
    constructor() {
        this.lastOperation = null;
    }

    flatten(arr) {
        this.lastOperation = 'flatten';
        return arr.reduce((flat, next) => flat.concat(next), []);
    }

    unique(arr) {
        this.lastOperation = 'unique';
        return [...new Set(arr)];
    }

    groupBy(arr, key) {
        this.lastOperation = 'groupBy';
        return arr.reduce((grouped, item) => {
            (grouped[item[key]] = grouped[item[key]] || []).push(item);
            return grouped;
        }, {});
    }
}

module.exports = new ArrayUtils();