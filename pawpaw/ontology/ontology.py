from __future__ import annotations
import dataclasses
import json
import typing

from pawpaw import Ito, Types, Errors
from pawpaw.arborform import Itorator

C_RULE = Itorator | Types.F_ITO_2_IT_ITOS
C_RULES = dict[str, C_RULE]
C_PATH = typing.Sequence[str]

class Discoveries(dict):
    def __init__(self, *args, **kwargs):
        self._itos: list[Ito] = list(kwargs.pop('itos', tuple()))
        dict.__init__(self, *args, **kwargs )

    @property
    def itos(self) -> list[Ito]:
        return self._itos   
    
    def __str__(self):
        c = ', '.join(f'{k}: {str(v)}' for k, v in self.items())
        return f'{{itos: {[str(i) for i in self._itos]}, {c}}}'
    
    def _flatten(self, filter_empties: bool = True, path: C_PATH = tuple()) -> dict[C_PATH, list[Ito]]:
        rv = {} if len(self.itos) == 0 and filter_empties else {tuple(path): self.itos}
        for key in self.keys():
            rv |= self[key]._flatten(filter_empties, path + (key,))
        return rv

    def flatten(self, filter_empties: bool = True) -> dict[C_PATH, list[Ito]]:
        return self._flatten(filter_empties, )
    
class Ontology(dict):
    def __missing__(self, key):
        if isinstance(key, typing.Sequence) and (lk := len(key)) > 0 and not isinstance(key, str):
            rv = self[key[0]]
            if lk > 1:
                rv = rv[key[1:]]
            return rv
        else:
            raise KeyError(key)

    def __init__(self, *args, **kwargs):
        self._rules: list[C_RULE] = kwargs.pop('rules', [])
        dict.__init__(self, *args, **kwargs )

    @property
    def rules(self) -> list[C_RULE]:
        return self._rules

    def __str__(self):
        c = ', '.join(f'{k}: {str(v)}' for k, v in self.items())
        return f'{{rules: {self._rules}, {c}}}'   
    
    def discover(self, *itos: Ito) -> Discoveries:
        rv = Discoveries()

        for rule in self._rules:
            for i in itos:
                rv.itos.extend(rule(i))

        for k, v in self.items():
            rv[k] = v.discover(*itos)

        return rv

class Query():

    # query := phrase [ &_or_| phrase ]...

    # phrase := [not] entity_or_query [quantifier]
    
    # not = !...

    # entity = [a-z\d_]+,  ⟦.+?⟧

    # quantifier = ?, +, *, {[n][,[m]]}

    # / / / /

    # penalty for interstitial entities (or non-ws characters) ~(ito_last.stop - ito_first.start) / sum(i.length for i in itos)


    mathematical_white_square_brackets = {
        'LEFT': '\u27E6',   # ⟦
        'RIGHT': '\u27E7',  # ⟧
    }

    class Term:
        _pat = r'''(?P<not>
                    !*
                )
                (?P<entity>
                    [a-z_]+
                    |
                    ⟦.+?⟧
                )
                (?P<quantifier>
                    \{
                        (?P<qty_min>\d+)?
                        (?:,(?P<qty_max>\d+)?)?
                    \}
                    |
                    (?P<symbol>
                        [?*+]
                    )
                )?'''

    # Terms optionally separated by spacing indicator: <

    def __init__(self, path: Types.C_QPATH):
        if isinstance(path, str):
            path = pawpaw.Ito(path)
        elif not isinstance(path, pawpaw.Ito):
            raise pawpaw.Errors.parameter_invalid_type('path', path, pawpaw.Types.C_QPATH)

        self._lbound = mathematical_white_square_brackets['LEFT']
        self._rbound = mathematical_white_square_brackets['RIGHT']

        self._re = regex.compile(_pat, regex.DOTALL | regex.VERBOSE)
        self._chain: list[term]