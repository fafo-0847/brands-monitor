/// <reference types="node" />
import { existsSync } from 'node:fs';
import { join } from 'node:path';

import type { ConfigContext, ExpoConfig } from 'expo/config';

// app.json holds the configuration. This file only adds the Firebase file for Android push
// notifications when it is present, so builds and `expo start` still work before it exists.
export default ({ config }: ConfigContext): ExpoConfig => {
  const googleServices = './google-services.json';
  const hasFirebase = existsSync(join(__dirname, googleServices));
  return {
    ...(config as ExpoConfig),
    android: {
      ...config.android,
      ...(hasFirebase ? { googleServicesFile: googleServices } : {}),
    },
  };
};
