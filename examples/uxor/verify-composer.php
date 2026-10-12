<?php
// Validate imported/retained vendor metadata against the consuming lock. The
// generated autoload fingerprint is recorded only after Composer runs its hooks.
function readJson(string $path): array {
    return json_decode(file_get_contents($path), true, flags: JSON_THROW_ON_ERROR);
}
try {
    if (($argv[1] ?? '') === 'has-hook') {
        exit(isset(readJson('composer.json')['scripts']['post-install-cmd']) ? 0 : 1);
    }
    if (($argv[1] ?? '') === 'fingerprint') {
        $files = ['composer.json', 'composer.lock', 'vendor/autoload.php', 'vendor/autoload_runtime.php'];
        foreach (glob('vendor/composer/*') ?: [] as $file) {
            if (is_file($file)) { $files[] = $file; }
        }
        sort($files);
        $hash = hash_init('sha256');
        foreach ($files as $file) {
            hash_update($hash, $file."\0".(is_file($file) ? hash_file('sha256', $file) : 'absent')."\0");
        }
        echo hash_final($hash), "\n";
        exit(0);
    }
    if (($argv[1] ?? '') !== 'verify') { throw new RuntimeException('Unknown verification mode'); }
    $lock = readJson('composer.lock');
    $installed = readJson('vendor/composer/installed.json');
    if (($installed['dev'] ?? false) !== true || !is_file('vendor/autoload.php') || !is_file('vendor/composer/installed.php')) {
        throw new RuntimeException('Development dependencies or generated autoloads are absent');
    }
    $expected = [];
    foreach (array_merge($lock['packages'] ?? [], $lock['packages-dev'] ?? []) as $package) { $expected[$package['name']] = $package; }
    if (isset($expected['symfony/runtime']) && !is_file('vendor/autoload_runtime.php')) {
        throw new RuntimeException('Symfony runtime autoload is absent');
    }
    $actual = [];
    foreach ($installed['packages'] ?? [] as $package) { $actual[$package['name']] = $package; }
    if (array_diff_key($expected, $actual) || array_diff_key($actual, $expected)) { throw new RuntimeException('Installed package set differs from composer.lock'); }
    $runtime = require 'vendor/composer/installed.php';
    foreach ($expected as $name => $package) {
        $found = $actual[$name];
        if ($package['version'] !== ($found['version'] ?? null)) { throw new RuntimeException("Installed version differs for $name"); }
        foreach (['source', 'dist'] as $type) {
            if (($package[$type]['reference'] ?? null) !== ($found[$type]['reference'] ?? null)) { throw new RuntimeException("Installed reference differs for $name"); }
        }
        $path = $found['install-path'] ?? null;
        if (($package['type'] ?? '') !== 'metapackage' && (!is_string($path) || !is_dir('vendor/composer/'.$path))) {
            throw new RuntimeException("Package directory missing for $name");
        }
        $record = $runtime['versions'][$name] ?? null;
        $method = $found['installation-source'] ?? 'dist';
        $reference = $package[$method]['reference'] ?? $package['source']['reference'] ?? $package['dist']['reference'] ?? null;
        if (!is_array($record) || ($record['pretty_version'] ?? null) !== $package['version'] || ($record['reference'] ?? null) !== $reference) {
            throw new RuntimeException("Runtime package metadata differs for $name");
        }
    }
    $loader = require 'vendor/autoload.php';
    if (!$loader instanceof Composer\Autoload\ClassLoader) { throw new RuntimeException('Composer autoloader did not initialize'); }
} catch (Throwable $error) {
    fwrite(STDERR, 'Composer reuse unavailable: '.$error->getMessage()."\n");
    exit(1);
}
