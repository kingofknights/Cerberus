"""
Contract master generation flows (input files are downloaded manually, see core/inputs.py).
"""

from flows.nse_cm_master_flow import nse_cm_contract_master_generation
from flows.nse_fo_master_flow import nse_fo_contract_master_generation
from flows.bse_cm_master_flow import bse_cm_contract_master_generation
from flows.bse_fo_master_flow import bse_fo_contract_master_generation
from flows.mcx_fo_master_flow import mcx_fo_contract_master_generation

__all__ = [
    "nse_cm_contract_master_generation",
    "nse_fo_contract_master_generation",
    "bse_cm_contract_master_generation",
    "bse_fo_contract_master_generation",
    "mcx_fo_contract_master_generation",
]
