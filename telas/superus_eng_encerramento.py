"""SIM SUPERUS · Encerramento de centro de custo (solicitação e aprovação)."""
from sim.ui import common as ui
from sim.ui.encerramento import tela_encerramento

ui.cabecalho("SUPERUS", "ENG", "Encerramento",
             "Solicite o encerramento da cobrança de um centro de custo ou, se tiver permissão, decida os pedidos.")
tela_encerramento("SUPERUS", "sup_enc")
