import { format } from '../utils/stringUtils';

class Logger {
    info(message) {
        console.info(format('%s: %s', 'INFO', message));
    }
    error(message) {
        console.error(format('%s: %s', 'ERROR', message));
    }
}

export default new Logger();