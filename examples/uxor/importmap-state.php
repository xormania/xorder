<?php
// Preserve Symfony-produced metadata; never infer dependency data from filenames.
use Symfony\Component\AssetMapper\ImportMap\ImportMapConfigReader;
use Symfony\Component\AssetMapper\ImportMap\RemotePackageStorage;

final class ImportmapState
{
    public function __construct(
        private readonly string $map,
        private readonly string $vendor,
        private readonly string $receipt = 'var/xorder/importmap-state.json',
    ) {}

    private function identity(): string
    {
        $lock = json_decode(file_get_contents('composer.lock'), true, flags: JSON_THROW_ON_ERROR);
        $mapper = null;
        foreach (array_merge($lock['packages'] ?? [], $lock['packages-dev'] ?? []) as $package) {
            if ($package['name'] === 'symfony/asset-mapper') {
                $mapper = [$package['version'], $package['source']['reference'] ?? null, $package['dist']['reference'] ?? null];
            }
        }
        if ($mapper === null) {
            throw new RuntimeException('symfony/asset-mapper is not in composer.lock');
        }
        return hash('sha256', json_encode([$this->map, hash_file('sha256', $this->map), $this->vendor, $mapper], JSON_THROW_ON_ERROR));
    }

    private function fileHash(string $file): string
    {
        $root = realpath($this->vendor);
        $path = realpath($file);
        if ($root === false || $path === false || !str_starts_with($path, $root.DIRECTORY_SEPARATOR) || !is_file($path)) {
            throw new RuntimeException('A required vendor asset is missing or outside the vendor directory');
        }
        return hash_file('sha256', $path);
    }

    private function write(string $path, string $bytes): void
    {
        if (!is_dir(dirname($path)) && !mkdir(dirname($path), 0777, true) && !is_dir(dirname($path))) {
            throw new RuntimeException('Cannot create asset state directory');
        }
        $temporary = tempnam(dirname($path), '.xorder-importmap-');
        if ($temporary === false) {
            throw new RuntimeException('Cannot stage asset state');
        }
        try {
            if (file_put_contents($temporary, $bytes) !== strlen($bytes) || !rename($temporary, $path)) {
                throw new RuntimeException('Cannot write asset state');
            }
        } finally {
            if (is_file($temporary)) { unlink($temporary); }
        }
    }

    public function restore(): void
    {
        $manifest = $this->vendor.'/installed.php';
        if (file_exists($manifest) || is_link($manifest) || !is_file($this->receipt)) {
            return;
        }
        try {
            $saved = json_decode(file_get_contents($this->receipt), true, flags: JSON_THROW_ON_ERROR);
            if (($saved['schema'] ?? null) !== 1 || ($saved['identity'] ?? null) !== $this->identity()
                || !is_array($saved['files'] ?? null) || !is_string($saved['metadata'] ?? null)) {
                return;
            }
            foreach ($saved['files'] as $file => $hash) {
                if (!is_string($file) || str_starts_with($file, '/') || in_array('..', explode('/', $file), true)
                    || $this->fileHash($this->vendor.'/'.$file) !== $hash) {
                    return;
                }
            }
            $bytes = base64_decode($saved['metadata'], true);
            if ($bytes === false) { return; }
            $this->write($manifest, $bytes);
            echo "Restored Symfony importmap metadata for unchanged vendor assets\n";
        } catch (Throwable) {
            // A missing/stale cache is not proof of installation. The normal
            // project hook or readiness repair below will use Symfony instead.
            fwrite(STDERR, "Importmap metadata cache unavailable; normal installation will be checked\n");
        }
    }

    public function inspect(): array
    {
        require_once 'vendor/autoload.php';
        $storage = new RemotePackageStorage($this->vendor);
        $reader = new ImportMapConfigReader($this->map, $storage);
        $entries = $reader->getEntries();
        $manifest = $this->vendor.'/installed.php';
        $installed = is_file($manifest) ? (static fn ($path) => require $path)($manifest) : [];
        if (!is_array($installed)) { throw new RuntimeException('Invalid importmap installation metadata'); }
        $files = [];
        $remote = false;
        foreach ($entries as $entry) {
            if (!$entry->isRemotePackage()) { continue; }
            $remote = true;
            $package = $installed[$entry->importName] ?? [];
            if (($package['version'] ?? null) !== $entry->version || !is_array($package['dependencies'] ?? null)
                || !is_array($package['extraFiles'] ?? [])) {
                throw new RuntimeException('Importmap installation metadata is missing or does not match the requested packages');
            }
            $paths = [$storage->getDownloadPath($entry->packageModuleSpecifier, $entry->type)];
            foreach ($package['extraFiles'] ?? [] as $extra) {
                $paths[] = $this->vendor.'/'.$entry->getPackageName().'/'.ltrim($extra, '/');
            }
            foreach ($paths as $path) {
                $files[substr($path, strlen($this->vendor) + 1)] = $this->fileHash($path);
            }
        }
        ksort($files);
        return $remote ? ['schema' => 1, 'identity' => $this->identity(), 'files' => $files,
                          'metadata' => base64_encode(file_get_contents($manifest))] : [];
    }

    public function record(): void
    {
        $state = $this->inspect();
        if (!$state) { return; }
        $bytes = json_encode($state, JSON_THROW_ON_ERROR | JSON_PRETTY_PRINT)."\n";
        if (!is_file($this->receipt) || file_get_contents($this->receipt) !== $bytes) {
            $this->write($this->receipt, $bytes);
        }
    }
}

try {
    $mode = $argv[1] ?? '';
    if (!in_array($mode, ['restore', 'verify', 'record'], true)) {
        throw new RuntimeException('Usage: importmap-state.php restore|verify|record');
    }
    $map = getenv('IMPORTMAP_FILE') ?: 'importmap.php';
    $vendor = rtrim(getenv('IMPORTMAP_VENDOR_DIR') ?: 'assets/vendor', '/');
    if (!is_file($map)) { exit(0); }
    $state = new ImportmapState($map, $vendor);
    match ($mode) {
        'restore' => $state->restore(),
        'verify' => $state->inspect(),
        'record' => $state->record(),
    };
} catch (Throwable $error) {
    fwrite(STDERR, 'Importmap readiness: '.$error->getMessage()."\n");
    exit(1);
}
