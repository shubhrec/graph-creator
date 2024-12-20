import dataService from '../services/dataService';
const arrayUtils = require('../utils/arrayUtils');
const { capitalize } = require('../utils/stringUtils');
import external from '../../lib/external';

class DataComponent {
    initialize() {
        this.service = dataService;
        this.utils = arrayUtils;
    }

    process(items) {
        const groups = this.utils.groupBy(items, 'category');
        Object.keys(groups).forEach(key => {
            groups[key] = groups[key].map(item => ({
                ...item,
                name: capitalize(item.name)
            }));
        });
        return external.process(groups);
    }
}

module.exports = new DataComponent();