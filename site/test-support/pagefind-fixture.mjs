// This module replaces only the Pagefind API boundary. The production search
// script imports it through the rendered form's data-index attribute.
let handlers;
export const calls = { options: [], search: [] };

export function configure({ options = async () => {}, search = async () => ({ results: [] }) } = {}) {
  handlers = { options, search };
  calls.options.length = calls.search.length = 0;
}

export async function options(value) {
  calls.options.push(value);
  return handlers.options(value);
}

export async function search(value) {
  calls.search.push(value);
  return handlers.search(value);
}
