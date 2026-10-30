/** @type {import('jest').Config} */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  setupFiles: ['<rootDir>/tests/setup.ts'],
  moduleNameMapper: {
    '^@rms/shared$': '<rootDir>/../../packages/shared/src/index.ts',
  },
};
