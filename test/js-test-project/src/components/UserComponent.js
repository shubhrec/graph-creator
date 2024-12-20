import dataService from '../services/dataService';
import apiService from '../services/apiService';
import { helper1 } from '../../lib/helpers';

class UserComponent {
    async fetchUserData(userId) {
        const data = await dataService
            .processData({ numbers: [[1, 2], [3, 4]], text: 'user' })
            .then(result => result.numbers)
            .catch(error => {
                helper1(error);
                return [];
            });

        return apiService.formatResponse({
            key: userId,
            value: data[0] || 0
        });
    }
}

export default new UserComponent();