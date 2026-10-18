<?php
require __DIR__.'/vendor/autoload.php';
function check(bool $ok, string $message): void {
    if (!$ok) { throw new RuntimeException($message); }
}
$formatted = (new NumberFormatter('en_US', NumberFormatter::DECIMAL))->format(1234.5);
check($formatted === '1,234.5', 'intl formatting');
check(mb_strlen('é') === 1, 'mbstring behavior');
check((new DOMDocument())->loadXML('<root><item>ok</item></root>'), 'DOM behavior');
check(bcadd('1.25', '2.75', 2) === '4.00', 'bcmath behavior');
check((new Redis())->connect('redis', 6379), 'Redis extension connection');
$db = new PDO(getenv('DATABASE_DSN'), 'fixture', 'fixture', [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$db->exec('CREATE TABLE IF NOT EXISTS image_checks (id integer primary key, value text not null)');
$db->exec("INSERT INTO image_checks VALUES (1, 'ready') ON CONFLICT (id) DO UPDATE SET value=EXCLUDED.value");
check($db->query('SELECT value FROM image_checks WHERE id=1')->fetchColumn() === 'ready', 'PostgreSQL round trip');
file_put_contents(__DIR__.'/workspace-proof.txt', "written by container\n");
$cache = getenv('XDG_CACHE_HOME') ?: getenv('HOME').'/.cache';
check(file_put_contents($cache.'/cache-proof', "cache writable\n") !== false, 'Cache writable');
check(!in_array('coverage', xdebug_info('mode'), true), 'Xdebug coverage is off by default');
check(extension_loaded('pcov') && !ini_get('pcov.enabled'), 'PCOV is present and disabled by default');
echo "PHP extensions, PostgreSQL, Redis and workspace passed\n";
