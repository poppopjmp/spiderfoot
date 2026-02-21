import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  client: '@hey-api/client-axios',
  input: 'openapi.json',
  output: 'src/api/generated',
});
