import re
from os import path

from django.conf import settings
from django.core.exceptions import ValidationError

ALIASES = {
    'yes': r'yes|yeah|sure|totally|of course|a little|ok|ya|probably|',
    'no': r'no|never|nope',
    'greeting': r'hi|hello|sup',
    'else': r'.*',
}


def parse_script(string):
    # XXX this whole thing is gross

    exchanges = {}
    string = string.replace('\r\n', '\n')

    for exchange in string.split('\n\n'):
        exchange = exchange.strip()
        lines = exchange.split('\n')
        slug = lines[0].lstrip('#').strip()

        if slug in exchanges:
            raise ValidationError('Duplicate exchange ID: "%s"' % slug)

        forks = []
        messages = []
        event = None
        goto = None
        seen_aliases = set()

        for line in lines[1:]:
            if line.startswith('>'):
                alias = line.split(':', 1)[0].lstrip('>').strip()
                target = line.split(':', 1)[1].lstrip('>').strip()

                seen_aliases.add(alias)

                if alias == 'null':
                    goto = target
                else:
                    regex = ALIASES.get(alias, alias)
                    forks.append((regex, target))

            elif line.startswith('*'):
                event = line.lstrip('*').strip()
            else:
                messages.append(line.strip())

        if (
            'null' not in seen_aliases and
            'else' not in seen_aliases and
            not event
        ):
            raise ValidationError('Exchange "%s" does not have an else' % slug)

        exchanges[slug] = {
            'forks': forks,
            'messages': messages,
            'event': event,
            'goto': goto
        }

    for host_slug, exchange in exchanges.iteritems():
        if exchange['goto']:
            if exchange['forks']:
                raise ValidationError('Exchange %s has null and non-null forks'
                                      % host_slug)

            if exchange['goto'] not in exchanges:
                raise ValidationError('No "%s" exchange ID (refernced in "%s")'
                                      % (exchange['goto'], host_slug))

            goto = exchanges[exchange['goto']]

            if goto['goto']:
                raise ValidationError(
                    "I am lazy and haven't implemented chaning nulls; talk to "
                    "me if you need this."
                )

            exchange['forks'] = goto['forks']
            exchange['messages'] = exchange['messages'] + goto['messages']

    # VALIDATE

    if 'initial' not in exchanges:
        raise ValidationError('No "initial" exchange ID')

    for host_slug, exchange in exchanges.iteritems():
        # XXX handle infinite loops
        if not (exchange['forks'] or exchange['event']):
            raise ValidationError("There's no way out of the \"%s\" exchange"
                                  % host_slug)

        for _, target_slug in exchange['forks']:
            if target_slug not in exchanges:
                raise ValidationError('No "{target}" exchange ID (referenced '
                                      'in "{host}")'.format(target=target_slug,
                                                            host=host_slug))

    return exchanges


PARTS = []

for part in ['part1.txt', 'part2.txt']:
    with open(path.join(settings.BASE_DIR, 'scripts', part)) as script_file:
        PARTS.append(parse_script(script_file.read()))


def get_next_exchange(script, current_slug, response):
    current_line = script[current_slug]

    for regex, slug in current_line['forks']:
        if re.findall(r'\b%s\b' % regex, response, flags=re.IGNORECASE):
            return slug
