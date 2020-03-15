"""
Copyright 2017 Robin Verschueren

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from cvxpy.reductions.cvx_attr2constr import convex_attributes
from cvxpy.constraints import NonPos, Zero
from cvxpy.reductions.solvers.solver import Solver, ConeDims
from cvxpy.reductions.utilities import group_constraints
from cvxpy.reductions.qp2quad_form.qp_matrix_stuffing import ParamQuadProg
import cvxpy.settings as s
import numpy as np
import scipy.sparse as sp


class QpSolver(Solver):
    """
    A QP solver interface.
    """
    # Every QP solver supports Zero and NonPos constraints.
    SUPPORTED_CONSTRAINTS = [Zero, NonPos]

    # Some solvers cannot solve problems that do not have constraints.
    # For such solvers, REQUIRES_CONSTR should be set to True.
    REQUIRES_CONSTR = False

    def accepts(self, problem):
        return (isinstance(problem, ParamQuadProg)
                and (self.MIP_CAPABLE or not problem.is_mixed_integer())
                and not convex_attributes([problem.x])
                and (len(problem.constraints) > 0 or not self.REQUIRES_CONSTR)
                and all(type(c) in self.SUPPORTED_CONSTRAINTS for c in
                        problem.constraints))

    def _prepare_data_and_inv_data(self, problem):
        data = {}
        inv_data = {self.VAR_ID: problem.x.id}

        constr_map = group_constraints(problem.constraints)
        data[QpSolver.DIMS] = ConeDims(constr_map)
        inv_data[QpSolver.DIMS] = data[QpSolver.DIMS]
        zero_constr = constr_map[Zero]
        neq_constr = constr_map[NonPos]
        inv_data[QpSolver.EQ_CONSTR] = zero_constr
        inv_data[QpSolver.NEQ_CONSTR] = neq_constr

        # Add information about integer variables
        inv_data['MIP'] = problem.is_mixed_integer()

        data[s.PARAM_PROB] = problem
        return problem, data, inv_data

    def apply(self, problem):
        """
        Construct QP problem data stored in a dictionary.
        The QP has the following form

            minimize      1/2 x' P x + q' x
            subject to    A x =  b
                          F x <= g

        """
        problem, data, inv_data = self._prepare_data_and_inv_data(problem)

        P, q, d, A, b = problem.apply_parameters()
        inv_data[s.OFFSET] = d
        # quadratic part of objective is x.T * P * x but solvers expect
        # 0.5*x.T * P * x.
        P = 2*P

        # Get number of variables
        n = x.size

        if eq_cons:
            eq_coeffs = list(zip(*[get_coeff_offset(con.expr)
                                   for con in eq_cons]))
            A = sp.vstack(eq_coeffs[0])
            b = - np.concatenate(eq_coeffs[1])
        else:
            A, b = sp.csr_matrix((0, n)), -np.array([])

        ineq_cons = [c for c in problem.constraints if type(c) == NonPos]
        if ineq_cons:
            ineq_coeffs = list(zip(*[get_coeff_offset(con.expr)
                                     for con in ineq_cons]))
            F = sp.vstack(ineq_coeffs[0])
            g = - np.concatenate(ineq_coeffs[1])
        else:
            F, g = sp.csr_matrix((0, n)), -np.array([])

        # Create dictionary with problem data
        data = {}
        data[s.P] = sp.csc_matrix(P)
        data[s.Q] = q
        data[s.A] = sp.csc_matrix(A)
        data[s.B] = b
        data[s.F] = sp.csc_matrix(F)
        data[s.G] = g
        data[s.BOOL_IDX] = [t[0] for t in problem.x.boolean_idx]
        data[s.INT_IDX] = [t[0] for t in problem.x.integer_idx]
        data['n_var'] = n
        data['n_eq'] = A.shape[0]
        data['n_ineq'] = F.shape[0]

        return data, inverse_data
