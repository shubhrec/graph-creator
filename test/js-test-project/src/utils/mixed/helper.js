const { log } = require('../logger');
import { capitalize } from '../stringUtils';
const arrayUtils = require('../arrayUtils');
import mathUtils from '../mathUtils';

export function processData(data) {
    log('Processing data');
    return {
        text: capitalize(data.text),
        numbers: arrayUtils.unique(data.numbers),
        sum: mathUtils.add(data.x, data.y)
    };
}