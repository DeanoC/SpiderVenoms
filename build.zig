const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const spider_protocol_dep = b.dependency("spider_protocol", .{
        .target = target,
        .optimize = optimize,
    });
    const spider_node_dep = b.dependency("spider_node", .{
        .target = target,
        .optimize = optimize,
    });
    const ziggy_tool_runtime_dep = b.dependency("ziggy_tool_runtime", .{
        .target = target,
        .optimize = optimize,
    });

    const spider_protocol_module = spider_protocol_dep.module("spider-protocol");
    const spiderweb_node_module = spider_node_dep.module("spiderweb_node");
    const ziggy_tool_runtime_module = ziggy_tool_runtime_dep.module("ziggy-tool-runtime");

    const local_service_mod = b.createModule(.{
        .root_source_file = b.path("src/local_service_main.zig"),
        .target = target,
        .optimize = optimize,
    });
    local_service_mod.addImport("spider-protocol", spider_protocol_module);
    local_service_mod.addImport("ziggy-tool-runtime", ziggy_tool_runtime_module);
    const local_service = b.addExecutable(.{
        .name = "spiderweb-local-service",
        .root_module = local_service_mod,
    });
    local_service.linkLibC();
    b.installArtifact(local_service);

    const computer_driver_mod = b.createModule(.{
        .root_source_file = spider_node_dep.path("examples/drivers/computer_driver.zig"),
        .target = target,
        .optimize = optimize,
    });
    computer_driver_mod.addImport("spiderweb_node", spiderweb_node_module);
    const computer_driver = b.addExecutable(.{
        .name = "spiderweb-computer-driver",
        .root_module = computer_driver_mod,
    });
    computer_driver.linkLibC();
    if (target.result.os.tag == .macos) {
        computer_driver.linkFramework("ApplicationServices");
    }
    b.installArtifact(computer_driver);

    const browser_driver_mod = b.createModule(.{
        .root_source_file = spider_node_dep.path("examples/drivers/browser_driver.zig"),
        .target = target,
        .optimize = optimize,
    });
    browser_driver_mod.addImport("spiderweb_node", spiderweb_node_module);
    const browser_driver = b.addExecutable(.{
        .name = "spiderweb-browser-driver",
        .root_module = browser_driver_mod,
    });
    browser_driver.linkLibC();
    if (target.result.os.tag == .macos) {
        browser_driver.linkFramework("ApplicationServices");
    }
    b.installArtifact(browser_driver);

    const managed_local_bundle_bin_dir = "share/spidervenoms/bundles/managed-local/bin";
    const install_bundle_local_service = b.addInstallFile(
        local_service.getEmittedBin(),
        managed_local_bundle_bin_dir ++ "/spiderweb-local-service",
    );
    const install_bundle_computer_driver = b.addInstallFile(
        computer_driver.getEmittedBin(),
        managed_local_bundle_bin_dir ++ "/spiderweb-computer-driver",
    );
    const install_bundle_browser_driver = b.addInstallFile(
        browser_driver.getEmittedBin(),
        managed_local_bundle_bin_dir ++ "/spiderweb-browser-driver",
    );
    b.getInstallStep().dependOn(&install_bundle_local_service.step);
    b.getInstallStep().dependOn(&install_bundle_computer_driver.step);
    b.getInstallStep().dependOn(&install_bundle_browser_driver.step);

    const assets = b.addInstallDirectory(.{
        .source_dir = b.path("assets"),
        .install_dir = .prefix,
        .install_subdir = "share/spidervenoms",
    });
    b.getInstallStep().dependOn(&assets.step);

    const install_assets = b.step("assets", "Install SpiderVenoms bundle assets");
    install_assets.dependOn(&assets.step);

    const bundle_step = b.step("bundle", "Install the managed local SpiderVenoms bundle");
    bundle_step.dependOn(&assets.step);
    bundle_step.dependOn(&install_bundle_local_service.step);
    bundle_step.dependOn(&install_bundle_computer_driver.step);
    bundle_step.dependOn(&install_bundle_browser_driver.step);

    const test_step = b.step("test", "Run SpiderVenoms tests");
    const local_service_tests = b.addTest(.{
        .root_module = local_service_mod,
    });
    local_service_tests.linkLibC();
    const run_local_service_tests = b.addRunArtifact(local_service_tests);
    test_step.dependOn(&run_local_service_tests.step);
}
