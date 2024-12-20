import serviceA from './serviceA';
import { log } from '../utils/logger';

class ServiceB {
    handle(data) {
        log(data);
        return serviceA.process();
    }
}

export default new ServiceB();