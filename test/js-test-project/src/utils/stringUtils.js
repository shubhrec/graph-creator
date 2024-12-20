// Arrow functions with different patterns
const capitalize = (str) => str.charAt(0).toUpperCase() + str.slice(1);

const trim = str => str.trim();

const format = (template, ...args) => {
    return template.replace(/%s/g, () => args.shift());
};

const split = (str, delimiter = ',') => str.split(delimiter);

module.exports = {
    capitalize,
    trim,
    format,
    split
};