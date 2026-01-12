/*
 * This file is part of the KubeVirt project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * Copyright The KubeVirt Authors.
 *
 */

package tests

import (
	"fmt"

	"kubevirt.io/kubevirt/tests/flags"
)

type ContainerDisk string

const (
	ContainerDiskCirrosCustomLocation ContainerDisk = "cirros-custom"
	ContainerDiskCirros               ContainerDisk = "cirros"
	ContainerDiskAlpine               ContainerDisk = "alpine"
	ContainerDiskAlpineTestTooling    ContainerDisk = "alpine-with-test-tooling"
	ContainerDiskFedoraTestTooling    ContainerDisk = "fedora-with-test-tooling"
	ContainerDiskVirtio               ContainerDisk = "virtio-container-disk"
	ContainerDiskEmpty                ContainerDisk = "empty"
	ContainerDiskFedoraRealtime       ContainerDisk = "fedora-realtime"
	KernelBoot                        ContainerDisk = "alpine-ext-kernel-boot-demo"
	KernelBootS390xGuestless          ContainerDisk = "kubevirt_s390x_guestless_loop"
)

const (
	FedoraVolumeSize = "6Gi"
	CirrosVolumeSize = "512Mi"
	AlpineVolumeSize = "512Mi"
	BlankVolumeSize  = "16Mi"
	VirtioVolumeSize = "750Mi"
)

type containerDiskSpec struct {
	image string
	tag   string
}

func (s containerDiskSpec) fullImage(registry string) string {
	tag := s.tag
	if tag == "" {
		tag = flags.KubeVirtUtilityVersionTag
	}

	return fmt.Sprintf("%s/%s:%s", registry, s.image, tag)
}

var containerDiskSpecs = map[ContainerDisk]containerDiskSpec{
	ContainerDiskCirros:               {image: fmt.Sprintf("%s-container-disk-demo", ContainerDiskCirros)},
	ContainerDiskAlpine:               {image: fmt.Sprintf("%s-container-disk-demo", ContainerDiskAlpine)},
	ContainerDiskCirrosCustomLocation: {image: fmt.Sprintf("%s-container-disk-demo", ContainerDiskCirrosCustomLocation)},
	ContainerDiskVirtio:               {image: string(ContainerDiskVirtio)},
	ContainerDiskFedoraTestTooling:    {image: fmt.Sprintf("%s-container-disk", ContainerDiskFedoraTestTooling)},
	ContainerDiskFedoraRealtime:       {image: fmt.Sprintf("%s-container-disk", ContainerDiskFedoraRealtime)},
	ContainerDiskAlpineTestTooling:    {image: fmt.Sprintf("%s-container-disk", ContainerDiskAlpineTestTooling)},
	KernelBoot:                        {image: string(KernelBoot)},
	KernelBootS390xGuestless:          {image: string(KernelBootS390xGuestless), tag: "latest"},
}

// ContainerDiskFor takes the name of an image and returns the full
// registry diks image path.
// Use the ContainerDisk* constants as input values.
func ContainerDiskFor(name ContainerDisk) string {
	return ContainerDiskFromRegistryFor(flags.KubeVirtUtilityRepoPrefix, name)
}

func DataVolumeImportUrlForContainerDisk(name ContainerDisk) string {
	return DataVolumeImportUrlFromRegistryForContainerDisk(flags.KubeVirtUtilityRepoPrefix, name)
}

func DataVolumeImportUrlFromRegistryForContainerDisk(registry string, name ContainerDisk) string {
	return fmt.Sprintf("docker://%s", ContainerDiskFromRegistryFor(registry, name))
}

func ContainerDiskFromRegistryFor(registry string, name ContainerDisk) string {
	spec, found := containerDiskSpecs[name]
	if !found {
		panic(fmt.Sprintf("Unsupported registry disk %s", name))
	}

	return spec.fullImage(registry)
}

func ContainerDiskSizeBySourceURL(url string) string {
	if url == DataVolumeImportUrlForContainerDisk(ContainerDiskFedoraTestTooling) ||
		url == DataVolumeImportUrlForContainerDisk(ContainerDiskFedoraRealtime) {
		return FedoraVolumeSize
	}

	return CirrosVolumeSize
}
