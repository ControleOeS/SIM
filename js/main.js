/** Ponto de entrada: escolhe o repositório e liga as telas ao roteador. */
import { config } from './config.js';
import { MockRepository } from './data/mock-repository.js';
import { ApiRepository } from './data/api-repository.js';
import { assertRepository } from './data/repository.js';
import { createRouter } from './ui/router.js';
import { createHomeScreen } from './ui/home.js';
import { createBMScreen } from './ui/bm-mensal.js';
import { createCadastroScreen } from './ui/cadastro.js';

const repo = assertRepository(
  config.dataSource === 'api' ? new ApiRepository(config.apiBaseUrl) : new MockRepository(),
);

document.getElementById('demo-banner').hidden = !repo.isDemo;

const screens = {};
const router = createRouter(screens);
const go = (name) => router.go(name);

screens.home = createHomeScreen({ go });
screens.bm = createBMScreen({ repo, go });
screens.cadastro = createCadastroScreen({ repo, go });

router.start();
