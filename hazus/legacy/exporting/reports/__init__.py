# -*- coding: utf-8 -*-
"""
    hazus
    ~~~~~

    FEMA developed module for analzying risk and loss from natural hazards.

    :copyright: © 2019 by FEMA's Natural Hazards and Risk Assesment Program.
    :license: cc, see LICENSE for more details.
    :author: James Raines; james.rainesii@fema.dhs.gov
"""

__version__ = '0.0.1'
__all__ = ['generate_report']

from .Eq_Report_Generator import generate_report