// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "ES5510DSPBackend.h"
#include <array>
#include <filesystem>
#include <string>

class ES5510FactoryPackageProvider final : public IValidatedFactoryPackageProvider {
public:
    static ES5510FactoryPackageProvider& instance();
    const trollfx::es5510::ValidatedEffectPackage* package_for_slot(
        trollfx::es5510::EffectSlot slot) const noexcept override;
    const char* slot_error(std::uint8_t slot) const noexcept;
    const std::filesystem::path& asset_root() const noexcept { return root_; }
    std::size_t available_count() const noexcept { return registry_.size(); }

private:
    ES5510FactoryPackageProvider();
    void load_index();
    std::filesystem::path discover_asset_root() const;
    std::filesystem::path root_;
    trollfx::es5510::EffectRegistry registry_;
    std::array<std::string, 51> errors_{};
};

// Resolve a host-installed provider first (used by verified native tests and
// authorized importers), otherwise initialize the production local asset store.
const IValidatedFactoryPackageProvider* TROLLfx_GetProductionFactoryPackageProvider();
