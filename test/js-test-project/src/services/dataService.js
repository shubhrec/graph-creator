import { add, multiply } from '../utils/mathUtils';
import { capitalize } from '../utils/stringUtils';
import arrayUtils from '../utils/arrayUtils';
import { helper1, helper2 } from '../../lib/helpers';

class DataService {
    processData(data) {
        const numbers = arrayUtils.flatten(data.numbers);
        const sum = add(numbers[0], numbers[1]);
        const product = multiply(sum, 2);
        
        const text = capitalize(data.text);
        helper1(text);
        
        return {
            numbers: arrayUtils.unique(numbers),
            text: text,
            result: product
        };
    }
}

export default new DataService();