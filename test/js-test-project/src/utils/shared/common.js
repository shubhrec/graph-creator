import { capitalize } from '../stringUtils';
const { log } = require('../logger');

export const processString = (str) => {
    log(`Processing: ${str}`);
    return capitalize(str);
};