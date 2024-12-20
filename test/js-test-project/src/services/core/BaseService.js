const LibLogger = require('../../../lib/utils/logger');
import { helper2 } from '../../../lib/helpers';

class BaseService {
    constructor() {
        this.logger = LibLogger;
        this.helper = helper2;
    }
}

export default BaseService;