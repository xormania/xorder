<?php
// Exercise the real Symfony downloader with a deterministic in-memory origin.
use Symfony\Component\AssetMapper\ImportMap\ImportMapConfigReader;
use Symfony\Component\AssetMapper\ImportMap\RemotePackageDownloader;
use Symfony\Component\AssetMapper\ImportMap\RemotePackageStorage;
use Symfony\Component\AssetMapper\ImportMap\Resolver\PackageResolverInterface;

$autoload = realpath($argv[1] ?? 'vendor/autoload.php');
if (!$autoload) { throw new RuntimeException('Supply the installed project autoloader'); }
require $autoload;
$helper = dirname(__DIR__, 3).'/examples/uxor/importmap-state.php';
$directory = sys_get_temp_dir().'/xorder-importmap-'.bin2hex(random_bytes(8));
mkdir($directory, 0777, true);
$originalDirectory = getcwd();

function check(bool $condition, string $message): void {
    if (!$condition) { throw new RuntimeException($message); }
}
function helper(string $mode, int $expected = 0): void {
    global $helper, $directory;
    // ZTS chdir() changes PHP's virtual cwd, not the cwd inherited by children.
    $process = proc_open([PHP_BINARY, $helper, $mode], [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes, $directory);
    check(is_resource($process), "Could not start the $mode helper");
    fclose($pipes[0]);
    $output = stream_get_contents($pipes[1]).stream_get_contents($pipes[2]);
    fclose($pipes[1]); fclose($pipes[2]);
    $status = proc_close($process);
    check($status === $expected, "$mode returned status $status, expected $expected: $output");
}
$resolver = new class implements PackageResolverInterface {
    public int $requests = 0;
    public function resolvePackages(array $packagesToRequire): array { throw new LogicException('Not used'); }
    public function downloadPackages(array $importMapEntries, ?callable $progressCallback = null): array {
        $this->requests++;
        $result = [];
        foreach ($importMapEntries as $name => $entry) {
            $result[$name] = ['content' => 'fixture '.$entry->version,
                             'dependencies' => ['dependency-preserved'],
                             'extraFiles' => ['fonts/icon.woff2' => 'fixture-font']];
        }
        return $result;
    }
};
$download = static function () use ($resolver): array {
    $storage = new RemotePackageStorage('assets/vendor');
    return (new RemotePackageDownloader($storage, new ImportMapConfigReader('importmap.php', $storage), $resolver))->downloadPackages();
};
$map = ['local' => ['path' => './assets/app.js'],
        'alias' => ['version' => '1.0.0', 'package_specifier' => '@fixture/js'],
        'stylesheet' => ['version' => '1.0.0', 'package_specifier' => '@fixture/theme/style.css', 'type' => 'css']];
$writeMap = static function () use (&$map): void { file_put_contents('importmap.php', '<?php return '.var_export($map, true).';'); };
try {
    chdir($directory);
    mkdir('vendor');
    file_put_contents('vendor/autoload.php', '<?php return require '.var_export($autoload, true).';');
    file_put_contents('composer.lock', json_encode(['packages' => [['name' => 'symfony/asset-mapper', 'version' => 'fixture-1']]]));
    $writeMap();
    helper('restore');
    helper('verify', 1);
    check(count($download()) === 2, 'Cold install did not download both remote entries');
    helper('record');
    $metadata = file_get_contents('assets/vendor/installed.php');
    $receipt = file_get_contents('var/xorder/importmap-state.json');
    helper('verify'); helper('record');
    check(file_get_contents('var/xorder/importmap-state.json') === $receipt, 'Unchanged installation changed receipt');
    check($download() === [] && $resolver->requests === 1, 'Warm installation downloaded again');

    unlink('assets/vendor/installed.php');
    helper('restore');
    check(file_get_contents('assets/vendor/installed.php') === $metadata, 'Restored metadata was altered');
    check($download() === [] && $resolver->requests === 1, 'Restoration caused downloads');
    $installed = require 'assets/vendor/installed.php';
    check($installed['alias']['dependencies'] === ['dependency-preserved'], 'Dependency mappings were lost');
    check($installed['stylesheet']['extraFiles'] === ['fonts/icon.woff2'], 'CSS extra files were lost');

    // A retained Composer installation must not hide missing asset bytes.
    unlink('assets/vendor/@fixture/theme/fonts/icon.woff2');
    helper('verify', 1);
    check(count($download()) === 1, 'Missing extra file did not repair exactly its package');
    helper('record');

    // Missing metadata can be restored only for the captured bytes and inputs.
    unlink('assets/vendor/installed.php');
    file_put_contents('assets/vendor/@fixture/js/js.index.js', 'changed bytes');
    helper('restore');
    check(!file_exists('assets/vendor/installed.php'), 'Changed bytes reused metadata');
    $download(); helper('record');
    unlink('assets/vendor/installed.php');
    $map['alias']['version'] = '2.0.0'; $writeMap();
    helper('restore');
    check(!file_exists('assets/vendor/installed.php'), 'Changed version reused old metadata');
    $download(); helper('record');

    unlink('assets/vendor/installed.php');
    file_put_contents('var/xorder/importmap-state.json', '{broken');
    helper('restore');
    check(!file_exists('assets/vendor/installed.php'), 'Corrupt cache fabricated metadata');
    unlink('var/xorder/importmap-state.json');
    helper('restore');
    check(!file_exists('assets/vendor/installed.php'), 'Unproven files fabricated metadata');
    $download(); helper('record'); helper('verify');
    echo "Importmap reuse: real Symfony cold/warm install, exact metadata recovery, CSS extras, changes and cache loss passed\n";
} finally {
    chdir($originalDirectory);
    $files = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($directory, FilesystemIterator::SKIP_DOTS), RecursiveIteratorIterator::CHILD_FIRST);
    foreach ($files as $file) { $file->isDir() ? rmdir($file->getPathname()) : unlink($file->getPathname()); }
    rmdir($directory);
}
