"""
.. module: historical.vpc.poller
    :platform: Unix
    :copyright: (c) 2017 by Netflix Inc., see AUTHORS for more
    :license: Apache, see LICENSE for more details.
.. author:: Kevin Glisson <kglisson@netflix.com>
"""
import os
import logging

from botocore.exceptions import ClientError

from raven_python_lambda import RavenLambdaWrapper
from cloudaux.aws.ec2 import describe_vpcs

from historical.constants import CURRENT_REGION, HISTORICAL_ROLE
from historical.vpc.models import vpc_polling_schema
from historical.common.accounts import get_historical_accounts
from historical.common.kinesis import produce_events

logging.basicConfig()
log = logging.getLogger("historical")
log.setLevel(logging.INFO)


@RavenLambdaWrapper()
def handler(event, context):
    """
    Historical security group event poller.

    This poller is run at a set interval in order to ensure that changes do not go undetected by historical.

    Historical pollers generate `polling events` which simulate changes. These polling events contain configuration
    data such as the account/region defining where the collector should attempt to gather data from.
    """
    log.debug('Running poller. Configuration: {}'.format(event))

    for account in get_historical_accounts():
        try:
            vpcs = describe_vpcs(
                account_number=account['id'],
                assume_role=HISTORICAL_ROLE,
                region=CURRENT_REGION
            )
            events = [vpc_polling_schema.serialize(account['id'], v) for v in vpcs['Vpcs']]
            produce_events(events, os.environ.get('HISTORICAL_STREAM', 'HistoricalVPCPollerStream'))
            log.debug('Finished generating polling events. Account: {} Events Created: {}'.format(account['id'], len(events)))
        except ClientError as e:
            log.warning('Unable to generate events for account. AccountId: {account_id} Reason: {reason}'.format(
                account_id=account['id'],
                reason=e
            ))

