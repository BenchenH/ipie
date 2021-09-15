from pyqumc.estimators.ueg import fock_ueg
from pyqumc.estimators.generic import fock_generic
from pyqumc.estimators.hubbard import fock_hubbard

def fock_matrix(system, G):
    if system.name == "UEG":
        return fock_ueg(system, G)
    elif system.name == "Generic":
        return fock_generic(system, G)
    elif system.name == "Hubbard":
        return fock_hubbard(system, G)
    else:
        print("# Fock matrix not implemented for {}".format(system.name))
        return None