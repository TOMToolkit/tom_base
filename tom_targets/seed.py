from tom_targets.models import Target, TargetList
from guardian.shortcuts import assign_perm
from django.contrib.auth.models import Group

messier_targets = [
    ("M1", 83.6330833, 22.0145),
    ("M2", 323.3625833, -0.82325),
    ("M3", 205.5484167, 28.3772778),
    ("M4", 245.89675, -26.52575),
    ("M5", 229.6384167, 2.0810278),
    ("M6", 265.0833, -32.2533),
    ("M7", 268.4625, -34.7933),
    ("M8", 270.9042, -24.3867),
    ("M9", 259.7990833, -18.51625),
    ("M10", 254.2877083, -4.1003056),
    ("M11", 282.7708, -6.27),
    ("M12", 251.8090833, -1.9485278),
    ("M13", 250.423475, 36.4613194),
    ("M14", 264.400625, -3.2459167),
    ("M15", 322.4930417, 12.167),
    ("M16", 274.7, -13.8067),
    ("M17", 275.1958, -16.1717),
    ("M18", 274.9917, -17.1017),
    ("M19", 255.6570417, -26.2679444),
    ("M20", 270.675, -22.9717),
    ("M21", 271.0542, -22.49),
    ("M22", 279.09975, -23.90475),
    ("M23", 269.2667, -18.985),
    ("M24", 274.2, -18.55),
    ("M25", 277.9458, -19.1167),
    ("M26", 281.325, -9.3833),
    ("M27", 299.9015792, 22.7210417),
    ("M28", 276.1370417, -24.8698333),
    ("M29", 305.9833, 38.5233),
    ("M30", 325.0921667, -23.1798611),
    ("M31", 10.6847083, 41.26875),
    ("M32", 10.6742708, 40.8651694),
    ("M33", 23.4621, 30.6599417),
    ("M34", 40.5208, 42.7617),
    ("M35", 92.225, 24.3333),
    ("M36", 84.075, 34.14),
    ("M37", 88.075, 32.5533),
    ("M38", 82.1792, 35.855),
    ("M39", 322.95, 48.4333),
    ("M40", 185.5522083, 58.0829444),
    ("M41", 101.5042, -20.7567),
    ("M42", 83.8220792, -5.3911111),
    ("M43", 83.8792, -5.27),
    ("M44", 130.1, 19.6667),
    ("M45", 56.75, 24.1167),
    ("M46", 115.4417, -14.81),
    ("M47", 114.1458, -14.4833),
    ("M48", 123.4292, -5.75),
    ("M49", 187.4449917, 8.0004111),
    ("M50", 105.6979208, -8.3377806),
    ("M51", 202.469575, 47.1952583),
    ("M52", 351.2, 61.5933),
    ("M53", 198.2302083, 18.1681667),
    ("M54", 283.763875, -30.4798611),
    ("M55", 294.9987917, -30.96475),
    ("M56", 289.1482083, 30.1834722),
    ("M57", 283.3961625, 33.029175),
    ("M58", 189.4316542, 11.8180889),
    ("M59", 190.509675, 11.6469306),
    ("M60", 190.9167, 11.5526111),
    ("M61", 185.4789583, 4.4735889),
    ("M62", 255.3025, -30.1123611),
    ("M63", 198.9555375, 42.0292889),
    ("M64", 194.1820667, 21.6826583),
    ("M65", 169.7331542, 13.0922111),
    ("M66", 170.0626083, 12.9912889),
    ("M67", 132.825, 11.8),
    ("M68", 189.8665833, -26.7440556),
    ("M69", 277.84625, -32.3480833),
    ("M70", 280.8031667, -32.2921111),
    ("M71", 298.4437083, 18.7791944),
    ("M72", 313.3654167, -12.5373056),
    ("M73", 314.75, -12.633),
    ("M74", 24.17405, 15.7834611),
    ("M75", 301.5201708, -21.9222611),
    ("M76", 25.5820417, 51.5754722),
    ("M77", 40.6698792, -0.0132889),
    ("M78", 86.6908292, 0.0791694),
    ("M79", 81.044125, -24.52425),
    ("M80", 244.2600417, -22.9760833),
    ("M81", 148.8882208, 69.0652944),
    ("M82", 148.9684583, 69.6797028),
    ("M83", 204.2538292, -29.8657611),
    ("M84", 186.2655958, 12.8869833),
    ("M85", 186.3502208, 18.1910806),
    ("M86", 186.549225, 12.9459694),
    ("M87", 187.7059292, 12.3911222),
    ("M88", 187.9967333, 14.4204111),
    ("M89", 188.9159, 12.5563),
    ("M90", 189.2075667, 13.1628694),
    ("M91", 188.860125, 14.4963194),
    ("M92", 259.2807917, 43.1359444),
    ("M93", 116.125, -23.8567),
    ("M94", 192.72145, 41.1201528),
    ("M95", 160.9905542, 11.7036111),
    ("M96", 161.6906, 11.8199389),
    ("M97", 168.6987542, 55.0190889),
    ("M98", 183.4512167, 14.9004694),
    ("M99", 184.7067708, 14.4164889),
    ("M100", 185.7287458, 15.8223806),
    ("M101", 210.8024292, 54.34875),
    ("M102", 226.6231708, 55.7633083),
    ("M103", 23.3458, 60.65),
    ("M104", 189.9976333, -11.6230556),
    ("M105", 161.9566667, 12.5816306),
    ("M106", 184.7400833, 47.3037194),
    ("M107", 248.13275, -13.0537778),
    ("M108", 167.8790417, 55.6741111),
    ("M109", 179.3999333, 53.3745194),
    ("M110", 10.0919792, 41.6853),
]


def seed_messier_targets():
    public, _ = Group.objects.get_or_create(name='Public')
    target_list, _ = TargetList.objects.get_or_create(name='Messier Catalog')
    for target in messier_targets:
        t, _ = Target.objects.get_or_create(name=target[0], ra=target[1], dec=target[2], type=Target.SIDEREAL)
        target_list.targets.add(t)
        assign_perm('tom_targets.view_target', public, t)
        assign_perm('tom_targets.change_target', public, t)
        assign_perm('tom_targets.delete_target', public, t)
