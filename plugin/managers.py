import itertools
from collections import defaultdict
from nanome.api.shapes import Label, Shape
from nanome.api.structure import Molecule
from nanome.api.interactions import Interaction
from nanome.util import enums, Color, Logs
from .models import InteractionShapesLine, InteractionStructure
from . import utils


class StructurePairManager:

    def __init__(self):
        super().__init__()
        self._data = defaultdict(list)

    @staticmethod
    def get_structpair_key(struct1_key, struct2_key):
        """Return a string key for the given atom indices."""
        structpair_key = '|'.join(sorted([str(struct1_key), str(struct2_key)]))
        return structpair_key

    @staticmethod
    def get_structpair_key_for_line(line):
        """Return a string key for the given atom indices."""
        sorted_atom1_idx_arr = sorted(line.atom1_idx_arr)
        sorted_atom2_idx_arr = sorted(line.atom2_idx_arr)
        struct1_key = ','.join([str(x) for x in sorted_atom1_idx_arr])
        struct2_key = ','.join([str(x) for x in sorted_atom2_idx_arr])
        structpair_key = '|'.join(sorted([struct1_key, struct2_key]))
        return structpair_key


class LabelManager(StructurePairManager):

    def all_labels(self):
        """Return a flat list of all lines being stored."""
        all_lines = []
        for structpair_key, label in sorted(self._data.items(), key=lambda keyval: keyval[0]):
            all_lines.append(self._data[structpair_key])
        return all_lines

    def add_label(self, label, struct1_index, struct2_index):
        if not isinstance(label, Label):
            raise TypeError(f'add_label() expected Label, received {type(label)}')
        structpair_key = self.get_structpair_key(struct1_index, struct2_index)
        self._data[structpair_key] = label

    def remove_label_for_structpair(self, struct1_index, struct2_index):
        """Remove all lines from data structure.

        Note that Shape.destroy() is not called, so lines still exist in workspace if uploaded.
        The label is returned, so that it can be destroyed at a later time.
        """
        key = self.get_structpair_key(struct1_index, struct2_index)
        label = None
        if key in self._data:
            label = self._data[key]
            del self._data[key]
        return label

    def clear(self):
        # Destroy all labels in workspace, and clear dict that's tracking them.
        labels = self.all_labels()
        if labels:
            Shape.destroy_multiple(labels)
        self._data = {}


class InteractionLineManager:
    """Organizes Interaction lines by atom pairs."""

    async def all_lines(self, **get_kwargs):
        """Return a flat list of all lines being stored."""
        all_lines = await Interaction.get(**get_kwargs)
        return all_lines

    def add_lines(self, line_list):
        pass

    def add_line(self, line):
        pass

    def get_lines_for_structure_pair(self, struct1: InteractionStructure, struct2: InteractionStructure, existing_lines=None):
        """Given two InteractionStructures, return all interaction lines connecting them.

        :arg struct1: InteractionStructure, or index str
        :arg struct2: InteractionStructure, or index str
        """
        struct_lines = []
        struct1_atom_indices = [int(x) for x in struct1.index.split(',')]
        struct2_atom_indices = [int(x) for x in struct2.index.split(',')]
        for line in existing_lines:
            struct1_is_line_atom1 = all(i in line.atom1_idx_arr for i in struct1_atom_indices)
            struct1_is_line_atom2 = all(i in line.atom2_idx_arr for i in struct1_atom_indices)
            if not struct1_is_line_atom1 and not struct1_is_line_atom2:
                continue

            struct2_is_line_atom1 = all(i in line.atom1_idx_arr for i in struct2_atom_indices)
            struct2_is_line_atom2 = all(i in line.atom2_idx_arr for i in struct2_atom_indices)
            if not struct2_is_line_atom1 and not struct2_is_line_atom2:
                continue

            # Confirm conformers match
            expected_struct1_conformation = line.atom1_conformation if struct1_is_line_atom1 else line.atom2_conformation
            expected_struct2_conformation = line.atom1_conformation if struct2_is_line_atom1 else line.atom2_conformation
            struct1_correct_conformer = struct1.conformer == expected_struct1_conformation
            struct2_correct_conformer = struct2.conformer == expected_struct2_conformation
            if struct1_correct_conformer and struct2_correct_conformer:
                struct_lines.append(line)

        return struct_lines

    def upload(self, line_list):
        """Upload multiple lines to Nanome."""
        Interaction.upload_multiple(line_list)

    @staticmethod
    def draw_interaction_line(struct1: InteractionStructure, struct2: InteractionStructure, kind: enums.InteractionKind, line_settings):
        """Draw line connecting two structs.

        :arg struct1: struct
        :arg struct2: struct
        :arg line_settings: Dict describing shape and color of line based on interaction_type
        """
        struct1_indices = []
        struct2_indices = []
        for struct1_index in struct1.index.split(','):
            struct1_indices.append(int(struct1_index))
        for struct2_index in struct2.index.split(','):
            struct2_indices.append(int(struct2_index))

        interaction_kind = kind
        atom1_conformation = struct1.conformer
        atom2_conformation = struct2.conformer
        line = Interaction(
            interaction_kind,
            struct1_indices,
            struct2_indices,
            atom1_conf=atom1_conformation,
            atom2_conf=atom2_conformation
        )
        line.visible = line_settings['visible']
        return line

    async def update_interaction_lines(self, interactions_data, complexes=None, **kwargs):
        """Update all interaction lines in workspace according to provided colors and visibility settings."""
        complexes = complexes or []
        get_kwargs = {}
        if complexes:
            mol_indices = [
                cmp.current_molecule.index
                for cmp in complexes
                if cmp.current_molecule is not None
            ]
            get_kwargs['molecules_idx'] = mol_indices
        interactions = await self.all_lines(**get_kwargs)
        lines_to_update = []
        for line in interactions:
            interaction_type = line.kind.name
            interaction_type_visible = interactions_data[interaction_type]['visible']
            if line.visible != interaction_type_visible:
                line.visible = interaction_type_visible
                lines_to_update.append(line)
        Logs.debug(f'Updating {len(lines_to_update)} lines')
        self.upload(lines_to_update)

    def destroy_lines(self, lines_to_delete):
        Interaction.destroy_multiple(lines_to_delete)


class ShapesLineManager(StructurePairManager):
    """Organizes Interaction lines by atom pairs."""

    async def all_lines(self, **kwargs):
        """Return a flat list of all lines being stored."""
        all_lines = []
        for _, line_list in sorted(self._data.items(), key=lambda keyval: keyval[0]):
            all_lines.extend(line_list)
        return all_lines

    def add_lines(self, line_list):
        for line in line_list:
            self.add_line(line)

    def add_line(self, line):
        if not isinstance(line, InteractionShapesLine):
            raise TypeError(f'add_line() expected InteractionLine, received {type(line)}')

        structpair_key = self.get_structpair_key_for_line(line)
        existing_interaction_kinds = [ln.kind for ln in self._data[structpair_key]]
        if line.kind not in existing_interaction_kinds:
            self._data[structpair_key].append(line)
            # Clear stream now that the line list is changing
            self._destroy_stream()

    def get_lines_for_structure_pair(self, struct1: InteractionStructure, struct2: InteractionStructure, *args, **kwargs):
        """Given two InteractionStructures, return all interaction lines connecting them.

        :arg struct1: InteractionStructure
        :arg struct2: InteractionStructure
        """
        key = self.get_structpair_key(struct1.index, struct2.index)
        return self._data[key]

    def upload(self, line_list):
        """Upload multiple lines to Nanome."""
        Shape.upload_multiple(line_list)

    @staticmethod
    def draw_interaction_line(
        struct1: InteractionStructure,
        struct2: InteractionStructure,
        kind: enums.InteractionKind,
            line_settings: dict) -> InteractionShapesLine:
        """Draw line connecting two structs.

        :arg struct1: struct
        :arg struct2: struct
        :arg line_settings: Dict describing shape and color of line based on interaction_type
        """
        line = InteractionShapesLine(struct1, struct2, **line_settings)
        line.kind = kind
        for struct, anchor in zip([struct1, struct2], line.anchors):
            anchor.anchor_type = enums.ShapeAnchorType.Atom
            anchor.target = struct.line_anchor.index
            # This nudges the line anchor to the center of the structure
            anchor.local_offset = struct.calculate_local_offset()
        return line

    async def update_interaction_lines(self, interactions_data, complexes=None, plugin=None):
        complexes = complexes or []
        stream_type = enums.StreamType.shape_color.value
        if not complexes:
            Logs.warning("No complexes to update, returning")
            return
        all_lines = await self.all_lines()
        line_indices = [line.index for line in all_lines]
        if not line_indices:
            Logs.warning("No interaction lines to update, returning")
            return
        if not getattr(self, '_stream', False):
            Logs.debug("Recreating Stream.")
            self._stream, _ = await plugin.create_writing_stream(line_indices, stream_type)
            if not self._stream:
                Logs.error("Failed to Create stream.")
                return
        new_colors = []
        in_frame_count = 0
        out_of_frame_count = 0

        for line in all_lines:
            # Make sure that both atoms connected by line are in frame.
            atom_iter = itertools.chain.from_iterable(cmp.current_molecule.atoms for cmp in complexes if cmp.current_molecule)
            line_is_in_frame = utils.line_in_frame(line, atom_iter)
            if line_is_in_frame:
                in_frame_count += 1
            else:
                out_of_frame_count += 1

            # Parse forms, and add line data to stream
            line_type = line.kind.name
            form_data = interactions_data[line_type]
            hide_interaction = not form_data['visible'] or not line_is_in_frame
            color = Color(*form_data['color'])

            color.a = 0 if hide_interaction else 255
            new_colors.extend(color.rgba)
            line.color = color
            self._update_line(line)

        # Logs.debug(f'in frame: {in_frame_count}')
        # Logs.debug(f'out of frame: {out_of_frame_count}')
        if self._stream:
            self._stream.update(new_colors)

    def destroy_lines(self, lines_to_delete):
        Shape.destroy_multiple(lines_to_delete)
        for line in lines_to_delete:
            structpair_key = self.get_structpair_key_for_line(line)
            if structpair_key in self._data:
                self._data[structpair_key].remove(line)
            else:
                Logs.warning("Line not found in manager while deleting.")

    def _destroy_stream(self):
        if getattr(self, '_stream', False):
            try:
                self._stream.destroy()
                del self._stream
            except KeyError:
                Logs.warning("Stream not found while destroying.")
                pass

    def _update_line(self, line):
        """Replace line stored in manager with updated version passed as arg."""
        structpair_key = self.get_structpair_key(*line.structure_indices)
        line_list = self._data[structpair_key]
        for i, stored_line in enumerate(line_list):
            if stored_line.index == line.index:
                line_list[i] = line
                break
