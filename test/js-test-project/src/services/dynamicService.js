class DynamicService {
    async loadModule(name) {
        const module = await import(`../utils/${name}`);
        return module.default;
    }
    
    async process(type, data) {
        const utils = await this.loadModule(type);
        return utils.process(data);
    }
}

export default new DynamicService();